"""Tests for the Lettermint webhook endpoint."""

import json
import logging
import time
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

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

    def test_tracking_disabled_acknowledges_without_storing(self, post_webhook):
        with patch("lettermint_django.tracking.enabled.apps.is_installed", return_value=False):
            response = post_webhook(webhook_payload("message.delivered"))
        assert response.status_code == 200
        assert response.json()["stored"] is False
        assert LmEmailEvent.objects.count() == 0


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
