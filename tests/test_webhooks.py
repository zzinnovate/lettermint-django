"""Tests for the Lettermint webhook endpoint."""

import json
import logging
import time
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from lettermint_django.bulk import send_bulk
from lettermint_django.models import LmEmailEvent, LmEmailMessage
from lettermint_django.signals import (
    lm_email_bounced,
    lm_email_delivered,
    lm_email_event,
    lm_email_failed,
)

from .conftest import sign_webhook, webhook_payload

URL = "/lettermint/message-events/"
DELIVERED_RESPONSE = {"status_code": 250, "enhanced_status_code": "2.0.0", "content": "250 2.0.0 OK"}
BOUNCE_RESPONSE = {"status_code": 550, "enhanced_status_code": "5.1.1", "content": "550 5.1.1 User unknown"}


@pytest.fixture
def sent_message():
    return LmEmailMessage.objects.create(
        message_id="msg_test_1",
        from_email="a@example.com",
        to=["recipient@example.com"],
        subject="Hello",
    )


class TestVerification:
    def test_rejects_missing_signature_headers(self, client):
        response = client.post(
            URL, data=json.dumps(webhook_payload("message.delivered")), content_type="application/json"
        )
        assert response.status_code == 400
        assert LmEmailEvent.objects.count() == 0

    def test_rejects_wrong_secret(self, post_webhook):
        response = post_webhook(webhook_payload("message.delivered"), secret="whsec_wrong")
        assert response.status_code == 400
        assert LmEmailEvent.objects.count() == 0

    def test_rejects_stale_timestamp(self, post_webhook):
        response = post_webhook(webhook_payload("message.delivered"), timestamp=int(time.time()) - 3600)
        assert response.status_code == 400

    def test_rejects_tampered_body(self, client):
        payload = webhook_payload("message.delivered")
        headers = sign_webhook(json.dumps(payload))
        payload["data"]["recipient"] = "attacker@example.com"
        response = client.post(
            URL, data=json.dumps(payload), content_type="application/json", headers=headers
        )
        assert response.status_code == 400

    def test_rejects_invalid_json(self, post_webhook):
        assert post_webhook("not json").status_code == 400

    def test_rejects_non_object_json(self, post_webhook):
        assert post_webhook("[1, 2]").status_code == 400

    def test_rejects_get(self, client):
        assert client.get(URL).status_code == 405

    def test_missing_secret_raises_improperly_configured(self, post_webhook, settings):
        settings.LETTERMINT_WEBHOOK_SECRET = "  "
        with pytest.raises(ImproperlyConfigured, match="LETTERMINT_WEBHOOK_SECRET"):
            post_webhook(webhook_payload("message.delivered"))

    def test_url_name(self):
        from django.urls import reverse

        assert reverse("lm-message-events") == URL


class TestEventStorage:
    def test_delivered_stores_event_and_updates_status(self, post_webhook, sent_message):
        response = post_webhook(webhook_payload("message.delivered", response=DELIVERED_RESPONSE))

        assert response.status_code == 200
        assert response.json() == {"received": True, "stored": True}

        event = LmEmailEvent.objects.get()
        assert event.event_id == "evt_1"
        assert event.email_message == sent_message
        assert event.message_id == "msg_test_1"
        assert event.event == "message.delivered"
        assert event.recipient == "recipient@example.com"
        assert event.reason == "250 2.0.0 OK"
        assert event.reason_code == "2.0.0"
        assert event.occurred_at == datetime(2026, 9, 1, 10, 0, tzinfo=dt_timezone.utc)
        assert event.data["response"] == DELIVERED_RESPONSE

        sent_message.refresh_from_db()
        assert sent_message.status == "delivered"
        assert sent_message.status_changed_at == event.occurred_at

    def test_hard_bounce(self, post_webhook, sent_message):
        post_webhook(webhook_payload("message.hard_bounced", response=BOUNCE_RESPONSE))

        sent_message.refresh_from_db()
        assert sent_message.status == "hard_bounced"
        assert sent_message.bounced is True

        event = LmEmailEvent.objects.get()
        assert event.is_bounce
        assert event.reason_code == "5.1.1"
        assert "User unknown" in event.reason

    def test_soft_bounce(self, post_webhook, sent_message):
        post_webhook(webhook_payload("message.soft_bounced", response={"status_code": 451}))
        sent_message.refresh_from_db()
        assert sent_message.status == "soft_bounced"

    def test_failed_uses_reason_fields(self, post_webhook, sent_message):
        post_webhook(
            webhook_payload(
                "message.failed",
                reason="Message rejected by policy",
                reason_code="policy_rejected",
                response={"status_code": 554},
            )
        )
        event = LmEmailEvent.objects.get()
        assert event.reason == "Message rejected by policy"
        assert event.reason_code == "policy_rejected"

        sent_message.refresh_from_db()
        assert sent_message.status == "failed"

    def test_duplicate_delivery_is_ignored(self, post_webhook, sent_message):
        payload = webhook_payload("message.delivered")
        assert post_webhook(payload).json()["stored"] is True

        second = post_webhook(payload)
        assert second.status_code == 200
        assert second.json()["stored"] is False
        assert LmEmailEvent.objects.count() == 1

    def test_unknown_message_still_stores_event(self, post_webhook):
        response = post_webhook(webhook_payload("message.hard_bounced", message_id="msg_from_elsewhere"))
        assert response.status_code == 200

        event = LmEmailEvent.objects.get()
        assert event.email_message is None
        assert event.message_id == "msg_from_elsewhere"
        assert LmEmailMessage.objects.count() == 0

    def test_older_event_does_not_regress_status(self, post_webhook, sent_message):
        post_webhook(webhook_payload("message.hard_bounced", event_id="evt_2", timestamp="2026-09-01T10:05:00Z"))
        post_webhook(webhook_payload("message.delivered", event_id="evt_1", timestamp="2026-09-01T10:00:00Z"))

        sent_message.refresh_from_db()
        assert sent_message.status == "hard_bounced"
        assert LmEmailEvent.objects.count() == 2

    def test_multiple_recipients_each_get_an_event(self, post_webhook, sent_message):
        post_webhook(webhook_payload("message.delivered", event_id="evt_a", recipient="a@example.com"))
        post_webhook(
            webhook_payload(
                "message.hard_bounced",
                event_id="evt_b",
                recipient="b@example.com",
                timestamp="2026-09-01T10:01:00Z",
            )
        )
        assert sent_message.events.count() == 2
        assert LmEmailEvent.objects.for_recipient("B@example.com").get().event == "message.hard_bounced"

    @pytest.mark.parametrize(
        "event_type, expected_status",
        [
            ("message.scheduled", "scheduled"),
            ("message.rescheduled", "scheduled"),
            ("message.released", "queued"),
            ("message.canceled", "canceled"),
        ],
    )
    def test_scheduling_events_update_status(self, post_webhook, sent_message, event_type, expected_status):
        post_webhook(webhook_payload(event_type))
        sent_message.refresh_from_db()
        assert sent_message.status == expected_status

    def test_canceled_message_is_not_delivered_and_not_in_transit(self, post_webhook, sent_message):
        post_webhook(webhook_payload("message.canceled"))
        assert LmEmailMessage.objects.not_delivered().get() == sent_message
        assert LmEmailMessage.objects.get().status == "canceled"

    def test_unknown_event_with_surprising_shape_is_stored_not_500(self, post_webhook, sent_message):
        payload = {
            "id": "evt_new",
            "event": "message.something_lettermint_invented",
            "timestamp": "not a timestamp",
            "context": {"scope": "team", "new_field": [1, 2, 3]},
            "brand_new_top_level": {"nested": True},
            "data": {
                "message_id": "msg_test_1",
                "recipient": {"email": "recipient@example.com", "name": "Structured now"},
                "reason": ["a", "list"],
                "response": "a string instead of an object",
                "future": {"deeply": {"nested": None}},
            },
        }
        response = post_webhook(payload)
        assert response.status_code == 200
        assert response.json() == {"received": True, "stored": True}

        event = LmEmailEvent.objects.get()
        assert event.event == "message.something_lettermint_invented"
        assert event.email_message == sent_message
        assert event.reason == "['a', 'list']"
        assert event.reason_code == ""
        assert event.data["future"] == {"deeply": {"nested": None}}
        assert event.occurred_at is not None
        sent_message.refresh_from_db()
        assert sent_message.status == "pending"

    def test_overlong_values_are_truncated_not_500(self, post_webhook):
        payload = webhook_payload("message." + "x" * 100, recipient="r" * 300 + "@example.com")
        assert post_webhook(payload).status_code == 200
        event = LmEmailEvent.objects.get()
        assert len(event.event) == 64
        assert len(event.recipient) == 254

    def test_unknown_event_without_message_id_is_acknowledged(self, post_webhook):
        payload = {"id": "evt_x", "event": "account.something_new", "timestamp": "2026-09-01T10:00:00Z", "data": {"foo": "bar"}}
        response = post_webhook(payload)
        assert response.status_code == 200
        assert response.json()["stored"] is False
        assert LmEmailEvent.objects.count() == 0

    def test_unmapped_event_is_stored_without_status_change(self, post_webhook, sent_message):
        post_webhook(webhook_payload("message.auto_replied"))
        sent_message.refresh_from_db()
        assert sent_message.status == "pending"
        assert LmEmailEvent.objects.get().status is None

    def test_webhook_test_event_is_acknowledged_not_stored(self, post_webhook):
        now = int(time.time())
        payload = {
            "id": "evt_test",
            "event": "webhook.test",
            "timestamp": now,
            "data": {"message": "This is a test", "webhook_id": "wh_1", "timestamp": now},
        }
        response = post_webhook(payload)
        assert response.status_code == 200
        assert response.json() == {"received": True, "stored": False}
        assert LmEmailEvent.objects.count() == 0

    def test_event_without_message_id_is_acknowledged_not_stored(self, post_webhook):
        payload = {
            "id": "evt_s",
            "event": "suppression.added",
            "timestamp": "2026-09-01T10:00:00Z",
            "data": {"email": "x@example.com"},
        }
        response = post_webhook(payload)
        assert response.status_code == 200
        assert response.json()["stored"] is False
        assert LmEmailEvent.objects.count() == 0

    def test_naive_timestamp_is_treated_as_utc(self, post_webhook):
        post_webhook(webhook_payload("message.delivered", timestamp="2026-09-01T10:00:00"))
        assert LmEmailEvent.objects.get().occurred_at == datetime(2026, 9, 1, 10, 0, tzinfo=dt_timezone.utc)

    def test_missing_optional_fields_are_tolerated(self, post_webhook):
        payload = {
            "id": "evt_min",
            "event": "message.delivered",
            "timestamp": "garbage",
            "data": {"message_id": "msg_min"},
        }
        assert post_webhook(payload).status_code == 200
        event = LmEmailEvent.objects.get()
        assert event.recipient == ""
        assert event.reason == ""
        assert event.occurred_at is not None

    def test_inbound_is_acknowledged_not_stored(self, post_webhook):
        payload = {
            "id": "evt_in",
            "event": "message.inbound",
            "timestamp": "2026-09-01T10:00:00Z",
            "data": {"message_id": "in_1", "from": "someone@example.com", "subject": "Hi", "body": {"text": "..."}, "raw": "..."},
        }
        response = post_webhook(payload)
        assert response.status_code == 200
        assert response.json() == {"received": True, "stored": False}
        assert LmEmailEvent.objects.count() == 0

    def test_bulk_sent_messages_are_found_through_their_bulk(self, post_webhook, settings, mock_lettermint):
        settings.EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
        _, _, builder = mock_lettermint
        builder.send_batch.side_effect = lambda payloads: [
            {"message_id": f"bulk_msg_{i}", "status": "pending"} for i, _ in enumerate(payloads)
        ]
        from django.core.mail import EmailMessage

        result = send_bulk(
            [EmailMessage(subject="S", body="B", from_email="a@example.com", to=[f"r{i}@example.com"]) for i in range(3)]
        )
        assert result.sent_count == 3

        post_webhook(webhook_payload("message.delivered", message_id="bulk_msg_0", event_id="e0", recipient="r0@example.com"))
        post_webhook(webhook_payload("message.hard_bounced", message_id="bulk_msg_1", event_id="e1", recipient="r1@example.com"))

        sent = LmEmailMessage.objects.from_bulk(result.bulk_id)
        assert sent.count() == 3
        assert list(sent.bounced().values_list("message_id", flat=True)) == ["bulk_msg_1"]
        assert set(sent.not_delivered().values_list("message_id", flat=True)) == {"bulk_msg_1", "bulk_msg_2"}
        assert LmEmailEvent.objects.from_bulk(result.bulk_id).count() == 2
        assert LmEmailEvent.objects.from_bulk(result.bulk_id).bounces().get().recipient == "r1@example.com"

    def test_tracking_disabled_acknowledges_without_storing(self, post_webhook):
        with patch("lettermint_django.tracking.enabled.apps.is_installed", return_value=False):
            response = post_webhook(webhook_payload("message.delivered"))
        assert response.status_code == 200
        assert response.json()["stored"] is False
        assert LmEmailEvent.objects.count() == 0


class TestWebhookPath:
    @pytest.fixture
    def custom_path(self, settings):
        """Point LETTERMINT_WEBHOOK_PATH elsewhere and reload the URLconfs, restoring afterwards."""
        import importlib

        from django.urls import clear_url_caches

        import lettermint_django.urls
        import tests.urls

        def apply(path):
            settings.LETTERMINT_WEBHOOK_PATH = path
            importlib.reload(lettermint_django.urls)
            importlib.reload(tests.urls)
            clear_url_caches()

        apply("lmnt/events/")
        yield
        apply(None)

    def test_default_path(self):
        from django.urls import reverse

        from lettermint_django.urls import get_webhook_path

        assert get_webhook_path() == "lettermint/message-events/"
        assert reverse("lm-message-events") == "/lettermint/message-events/"

    @pytest.mark.parametrize("value, expected", [("/lmnt/events/", "lmnt/events/"), ("  hooks/lm  ", "hooks/lm"), ("", "lettermint/message-events/"), (None, "lettermint/message-events/")])
    def test_get_webhook_path_normalises(self, settings, value, expected):
        from lettermint_django.urls import get_webhook_path

        settings.LETTERMINT_WEBHOOK_PATH = value
        assert get_webhook_path() == expected

    def test_custom_path_serves_the_webhook(self, custom_path, client, sent_message):
        from django.urls import reverse

        assert reverse("lm-message-events") == "/lmnt/events/"
        body = json.dumps(webhook_payload("message.delivered"))
        response = client.post("/lmnt/events/", data=body, content_type="application/json", headers=sign_webhook(body))
        assert response.status_code == 200
        assert client.post(URL, data=body, content_type="application/json", headers=sign_webhook(body)).status_code == 404

    def test_secret_check_is_silent_without_webhook_urls(self, settings):
        from django.urls import clear_url_caches

        from lettermint_django.checks import check_webhook_secret

        settings.ROOT_URLCONF = "tests.urls_empty"
        settings.LETTERMINT_WEBHOOK_SECRET = ""
        clear_url_caches()
        try:
            assert check_webhook_secret(None) == []
        finally:
            clear_url_caches()


class TestWebhookSecretCheck:
    def test_passes_with_secret(self):
        from lettermint_django.checks import check_webhook_secret

        assert check_webhook_secret(None) == []

    @pytest.mark.parametrize("secret", [None, "", "   "])
    def test_warns_without_secret(self, settings, secret):
        from lettermint_django.checks import check_webhook_secret

        settings.LETTERMINT_WEBHOOK_SECRET = secret
        warnings = check_webhook_secret(None)
        assert [w.id for w in warnings] == ["lettermint_django.W002"]
        assert "/lettermint/message-events/" in warnings[0].msg
        assert "LETTERMINT_WEBHOOK_SECRET" in warnings[0].hint


class TestSignals:
    @pytest.fixture
    def received(self):
        calls = []

        def make(name):
            def receiver(sender, **kwargs):
                calls.append((name, sender, kwargs))

            return receiver

        receivers = {
            lm_email_event: make("event"),
            lm_email_delivered: make("delivered"),
            lm_email_bounced: make("bounced"),
            lm_email_failed: make("failed"),
        }
        for signal, receiver in receivers.items():
            signal.connect(receiver)
        yield calls
        for signal, receiver in receivers.items():
            signal.disconnect(receiver)

    def test_delivered_emits_generic_and_specific(self, post_webhook, sent_message, received):
        post_webhook(webhook_payload("message.delivered"))

        assert [name for name, _, _ in received] == ["event", "delivered"]
        _, sender, kwargs = received[1]
        assert sender is LmEmailEvent
        assert kwargs["event"].event == "message.delivered"
        assert kwargs["email_message"] == sent_message

    @pytest.mark.parametrize("event_type", ["message.soft_bounced", "message.hard_bounced"])
    def test_bounces_emit_bounced(self, post_webhook, sent_message, received, event_type):
        post_webhook(webhook_payload(event_type))
        assert [name for name, _, _ in received] == ["event", "bounced"]

    def test_failed_emits_failed(self, post_webhook, sent_message, received):
        post_webhook(webhook_payload("message.failed", reason="x", reason_code="y"))
        assert [name for name, _, _ in received] == ["event", "failed"]

    def test_unmapped_event_emits_generic_only(self, post_webhook, sent_message, received):
        post_webhook(webhook_payload("message.opened"))
        assert [name for name, _, _ in received] == ["event"]

    def test_unknown_message_passes_none_email_message(self, post_webhook, received):
        post_webhook(webhook_payload("message.hard_bounced", message_id="msg_other"))
        assert received[1][2]["email_message"] is None

    def test_duplicate_delivery_does_not_emit_again(self, post_webhook, sent_message, received):
        payload = webhook_payload("message.delivered")
        post_webhook(payload)
        post_webhook(payload)
        assert len(received) == 2

    def test_receiver_exception_is_logged_not_raised(self, post_webhook, sent_message, caplog):
        def broken(sender, **kwargs):
            raise RuntimeError("boom")

        lm_email_event.connect(broken)
        try:
            with caplog.at_level(logging.ERROR, logger="lettermint_django"):
                response = post_webhook(webhook_payload("message.delivered"))
        finally:
            lm_email_event.disconnect(broken)

        assert response.status_code == 200
        assert "Signal receiver" in caplog.text
        assert LmEmailEvent.objects.count() == 1
