"""Tests for message capture on send (backend -> LmEmailMessage)."""

import logging
from unittest.mock import patch

import pytest
from django.core.mail import EmailMessage

from lettermint_django import LettermintEmailBackend
from lettermint_django.models import LmEmailMessage
from lettermint_django.tracking.store_address import store_address

from .conftest import sent_payload


class TestRecordOnSend:
    def test_send_creates_lm_email_message(self, simple_email, mock_lettermint):
        assert LettermintEmailBackend().send_messages([simple_email]) == 1

        msg = LmEmailMessage.objects.get()
        assert msg.message_id == "msg_test_1"
        assert msg.status == "pending"
        assert msg.from_email == "Sender <sender@example.com>"
        assert msg.to == ["recipient@example.com"]
        assert msg.cc == []
        assert msg.bcc == []
        assert msg.subject == "Hello"
        assert msg.route == ""
        assert msg.bulk_id == ""
        assert msg.status_changed_at is None

    def test_records_route_cc_and_bcc(self, mock_lettermint, settings):
        settings.LETTERMINT_ROUTE = "transactional"
        email = EmailMessage(
            subject="S",
            body="B",
            from_email="a@example.com",
            to=["t@example.com"],
            cc=["c@example.com"],
            bcc=["b@example.com"],
        )
        LettermintEmailBackend().send_messages([email])

        msg = LmEmailMessage.objects.get()
        assert msg.route == "transactional"
        assert msg.cc == ["c@example.com"]
        assert msg.bcc == ["b@example.com"]

    def test_per_message_route_header_is_recorded(self, simple_email, mock_lettermint):
        simple_email.extra_headers["X-Lettermint-Route"] = "marketing"
        LettermintEmailBackend().send_messages([simple_email])
        assert LmEmailMessage.objects.get().route == "marketing"

    def test_stores_normalized_default_from_email(self, mock_lettermint):
        email = EmailMessage(subject="S", body="B", to=["t@example.com"])
        LettermintEmailBackend().send_messages([email])
        assert LmEmailMessage.objects.get().from_email == "Test <noreply@example.com>"

    def test_stores_status_from_response(self, simple_email, mock_lettermint):
        _, _, emails = mock_lettermint
        emails.send.return_value = {"message_id": "msg_q", "status": "queued"}
        LettermintEmailBackend().send_messages([simple_email])
        assert LmEmailMessage.objects.get().status == "queued"

    def test_scheduled_status_from_response_is_stored(self, simple_email, mock_lettermint):
        _, _, emails = mock_lettermint
        emails.send.return_value = {"message_id": "msg_s", "status": "scheduled", "scheduled_at": "2026-09-03T09:00:00Z"}
        LettermintEmailBackend().send_messages([simple_email])
        assert LmEmailMessage.objects.get().status == "scheduled"

    def test_unknown_status_falls_back_to_pending(self, simple_email, mock_lettermint):
        _, _, emails = mock_lettermint
        emails.send.return_value = {"message_id": "msg_q", "status": "something-new"}
        LettermintEmailBackend().send_messages([simple_email])
        assert LmEmailMessage.objects.get().status == "pending"

    def test_each_message_in_a_batch_is_recorded(self, mock_lettermint):
        _, _, emails = mock_lettermint
        emails.send.side_effect = [
            {"message_id": "m1", "status": "pending"},
            {"message_id": "m2", "status": "pending"},
        ]
        emails = [
            EmailMessage(subject="1", body="B", from_email="a@example.com", to=["x@example.com"]),
            EmailMessage(subject="2", body="B", from_email="a@example.com", to=["y@example.com"]),
        ]
        assert LettermintEmailBackend().send_messages(emails) == 2
        assert set(LmEmailMessage.objects.values_list("message_id", flat=True)) == {"m1", "m2"}

    def test_response_without_message_id_records_nothing(self, simple_email, mock_lettermint, caplog):
        _, _, emails = mock_lettermint
        emails.send.return_value = {}
        with caplog.at_level(logging.WARNING, logger="lettermint_django"):
            assert LettermintEmailBackend().send_messages([simple_email]) == 1
        assert LmEmailMessage.objects.count() == 0
        assert "no message_id" in caplog.text

    def test_nothing_recorded_when_app_not_installed(self, simple_email, mock_lettermint):
        with patch("lettermint_django.tracking.enabled.apps.is_installed", return_value=False):
            assert LettermintEmailBackend().send_messages([simple_email]) == 1
        assert LmEmailMessage.objects.count() == 0

    def test_database_error_does_not_break_send(self, simple_email, mock_lettermint, caplog):
        with patch.object(LmEmailMessage.objects, "create", side_effect=RuntimeError("db down")):
            with caplog.at_level(logging.ERROR, logger="lettermint_django"):
                assert LettermintEmailBackend().send_messages([simple_email]) == 1
        assert "Failed to record sent Lettermint message msg_test_1" in caplog.text
        assert LmEmailMessage.objects.count() == 0

    def test_duplicate_message_id_is_logged_and_transaction_stays_usable(
        self, simple_email, mock_lettermint, caplog
    ):
        backend = LettermintEmailBackend()
        backend.send_messages([simple_email])
        with caplog.at_level(logging.ERROR, logger="lettermint_django"):
            assert backend.send_messages([simple_email]) == 1
        assert "Failed to record sent Lettermint message msg_test_1" in caplog.text
        # The savepoint rolled back, so the surrounding transaction still works.
        assert LmEmailMessage.objects.count() == 1


class TestTrackingSwitch:
    def test_setting_off_records_nothing(self, simple_email, mock_lettermint, settings):
        settings.LETTERMINT_TRACKING = False
        assert LettermintEmailBackend().send_messages([simple_email]) == 1
        assert LmEmailMessage.objects.count() == 0


class TestTrackHeader:
    @pytest.mark.parametrize("value", ["false", "0", "no", "off", " FALSE ", "Off"])
    def test_header_off_records_nothing_and_stays_out_of_the_payload(self, simple_email, mock_lettermint, value):
        _, _, emails = mock_lettermint
        simple_email.extra_headers["X-Lettermint-Track"] = value
        simple_email.extra_headers["X-Custom"] = "kept"

        assert LettermintEmailBackend().send_messages([simple_email]) == 1

        assert LmEmailMessage.objects.count() == 0
        assert sent_payload(emails)["headers"] == {"X-Custom": "kept"}

    @pytest.mark.parametrize("value", ["true", "1", "yes", ""])
    def test_other_values_keep_tracking(self, simple_email, mock_lettermint, value):
        simple_email.extra_headers["X-Lettermint-Track"] = value
        LettermintEmailBackend().send_messages([simple_email])
        assert LmEmailMessage.objects.count() == 1

    def test_build_payload_drops_the_header(self, simple_email):
        simple_email.extra_headers["X-Lettermint-Track"] = "false"
        assert "headers" not in LettermintEmailBackend().build_payload(simple_email)


class TestStoreLess:
    def test_subject_off_stores_empty_subject(self, simple_email, mock_lettermint, settings):
        settings.LETTERMINT_TRACKING_SUBJECT = False
        LettermintEmailBackend().send_messages([simple_email])
        assert LmEmailMessage.objects.get().subject == ""

    def test_hashed_recipients(self, mock_lettermint, settings):
        settings.LETTERMINT_TRACKING_RECIPIENTS = "hashed"
        email = EmailMessage(
            subject="S",
            body="B",
            from_email="a@example.com",
            to=["Ann <Ann@Example.com>"],
            cc=["c@example.com"],
            bcc=["b@example.com"],
        )
        LettermintEmailBackend().send_messages([email])

        msg = LmEmailMessage.objects.get()
        assert msg.to == [store_address("ann@example.com")]
        assert msg.cc == [store_address("c@example.com")]
        assert msg.bcc == [store_address("b@example.com")]
        assert len(msg.to[0]) == 64 and "@" not in msg.to[0]
        assert msg.from_email == "a@example.com"


class TestStoreAddress:
    def test_plain_is_unchanged(self):
        assert store_address("Ann <ann@example.com>") == "Ann <ann@example.com>"
        assert store_address(None) == ""

    def test_hashed_ignores_case_whitespace_and_display_name(self, settings):
        settings.LETTERMINT_TRACKING_RECIPIENTS = "hashed"
        assert store_address(" ANN@example.com ") == store_address("Ann <ann@example.com>")
        assert store_address("ann@example.com") != store_address("bob@example.com")
        assert store_address("") == ""

    def test_hash_key_falls_back_to_secret_key(self, settings):
        settings.LETTERMINT_TRACKING_RECIPIENTS = "hashed"
        with_secret_key = store_address("ann@example.com")
        settings.LETTERMINT_TRACKING_HASH_KEY = "another-key"
        assert store_address("ann@example.com") != with_secret_key
