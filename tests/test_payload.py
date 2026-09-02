"""Tests for the backend's payload builder and batch primitives."""

import base64
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives

from lettermint_django import LettermintEmailBackend
from lettermint_django.models import LmEmailMessage


def full_message():
    msg = EmailMultiAlternatives(
        subject="Subject",
        body="Text body",
        from_email="Sender <sender@example.com>",
        to=["a@example.com", "b@example.com"],
        cc=["c@example.com"],
        bcc=["d@example.com"],
        reply_to=["reply@example.com", "ignored@example.com"],
        headers={"X-Custom": "1", "X-Lettermint-Route": "marketing", "X-Lettermint-Tag": "campaign-1"},
    )
    msg.attach_alternative("<b>html</b>", "text/html")
    msg.attach("file.txt", b"hello", "text/plain")
    return msg


class TestBuildPayload:
    def test_full_message(self):
        payload = LettermintEmailBackend().build_payload(full_message())
        assert payload == {
            "from": "Sender <sender@example.com>",
            "to": ["a@example.com", "b@example.com"],
            "cc": ["c@example.com"],
            "bcc": ["d@example.com"],
            "reply_to": ["reply@example.com"],
            "route": "marketing",
            "subject": "Subject",
            "text": "Text body",
            "html": "<b>html</b>",
            "headers": {"X-Custom": "1"},
            "tag": "campaign-1",
            "attachments": [{"filename": "file.txt", "content": base64.b64encode(b"hello").decode()}],
        }

    def test_minimal_message_uses_defaults(self, settings):
        settings.LETTERMINT_ROUTE = "default-route"
        payload = LettermintEmailBackend().build_payload(EmailMessage(subject="S", body="B", to=["t@example.com"]))
        assert payload == {
            "from": "Test <noreply@example.com>",
            "to": ["t@example.com"],
            "route": "default-route",
            "subject": "S",
            "text": "B",
        }

    def test_lettermint_headers_never_pass_through(self):
        msg = EmailMessage(subject="S", body="B", to=["t@example.com"], headers={"X-Lettermint-Tag": "  t  "})
        payload = LettermintEmailBackend().build_payload(msg)
        assert payload["tag"] == "t"
        assert "headers" not in payload

    def test_subclass_header_hook_applies_to_payload(self):
        class TrackingBackend(LettermintEmailBackend):
            def _get_passthrough_headers(self, email_message):
                headers = super()._get_passthrough_headers(email_message)
                headers.setdefault("X-LM-Override-Track-Opens", "true")
                return headers

        payload = TrackingBackend().build_payload(EmailMessage(subject="S", body="B", to=["t@example.com"]))
        assert payload["headers"] == {"X-LM-Override-Track-Opens": "true"}


class TestSendSingle:
    def test_returns_response_and_records_tag(self, mock_lettermint):
        backend = LettermintEmailBackend()
        backend.open()
        response = backend.send_single(full_message())
        assert response == {"message_id": "msg_test_1", "status": "pending"}

        stored = LmEmailMessage.objects.get()
        assert stored.tag == "campaign-1"
        assert stored.route == "marketing"
        assert LmEmailMessage.objects.tagged("campaign-1").count() == 1
        mock_lettermint[2].tag.assert_called_once_with("campaign-1")

    def test_no_recipients_returns_none(self, mock_lettermint):
        backend = LettermintEmailBackend()
        backend.open()
        assert backend.send_single(EmailMessage(subject="S", body="B")) is None

    def test_empty_response_still_counts_as_sent(self, simple_email, mock_lettermint):
        mock_lettermint[2].send.return_value = {}
        assert LettermintEmailBackend().send_messages([simple_email]) == 1

    def test_legacy_alias(self):
        assert LettermintEmailBackend._send is LettermintEmailBackend.send_single


class TestSendPayloads:
    def test_posts_batch_and_returns_responses(self, mock_lettermint):
        _, _, builder = mock_lettermint
        builder.send_batch.return_value = [{"message_id": "m1", "status": "pending"}]
        backend = LettermintEmailBackend()
        payloads = [{"from": "a@example.com", "to": ["b@example.com"], "subject": "S", "text": "B"}]

        assert backend.send_payloads(payloads) == [{"message_id": "m1", "status": "pending"}]
        builder.send_batch.assert_called_once_with(payloads)

    def test_empty_is_noop(self, mock_lettermint):
        assert LettermintEmailBackend().send_payloads([]) == []
        mock_lettermint[0].assert_not_called()

    def test_does_not_cap_batch_size(self, mock_lettermint):
        _, _, builder = mock_lettermint
        builder.send_batch.return_value = []
        LettermintEmailBackend().send_payloads([{"from": "a@example.com"}] * 1200)
        assert len(builder.send_batch.call_args.args[0]) == 1200

    def test_missing_api_key_raises(self, settings, mock_lettermint):
        settings.LETTERMINT_API_KEY = None
        with pytest.raises(ImproperlyConfigured):
            LettermintEmailBackend().send_payloads([{"from": "a@example.com"}])

    def test_fail_silently_without_key_raises_improperly_configured(self, settings, mock_lettermint):
        settings.LETTERMINT_API_KEY = None
        with pytest.raises(ImproperlyConfigured, match="could not be opened"):
            LettermintEmailBackend(fail_silently=True).send_payloads([{"from": "a@example.com"}])
