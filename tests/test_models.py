"""Tests for tracking models, querysets and the admin registration."""

from django.contrib import admin
from django.utils import timezone

from lettermint_django.models import LmEmailEvent, LmEmailMessage, LmMessageStatus


def make_message(message_id, status=LmMessageStatus.PENDING):
    return LmEmailMessage.objects.create(
        message_id=message_id, from_email="a@example.com", to=["r@example.com"], status=status
    )


def make_event(event_id, message, event, recipient=""):
    return LmEmailEvent.objects.create(
        event_id=event_id,
        email_message=message,
        message_id=message.message_id,
        event=event,
        recipient=recipient,
        occurred_at=timezone.now(),
    )


class TestLmEmailMessage:
    def test_status_filters(self):
        make_message("m1", "delivered")
        make_message("m2", "hard_bounced")
        make_message("m3", "soft_bounced")
        make_message("m4", "failed")
        make_message("m5")

        ids = lambda qs: set(qs.values_list("message_id", flat=True))  # noqa: E731
        assert ids(LmEmailMessage.objects.delivered()) == {"m1"}
        assert ids(LmEmailMessage.objects.bounced()) == {"m2", "m3"}
        assert ids(LmEmailMessage.objects.failed()) == {"m4"}

    def test_get_status(self):
        make_message("m1", "delivered")
        assert LmEmailMessage.objects.get_status("m1") == "delivered"
        assert LmEmailMessage.objects.get_status("unknown") is None

    def test_str_and_bounced(self):
        msg = make_message("m1", "hard_bounced")
        assert str(msg) == "m1 (hard_bounced)"
        assert msg.bounced is True
        assert make_message("m2", "delivered").bounced is False

    def test_message_id_is_unique(self):
        import pytest
        from django.db import IntegrityError, transaction

        make_message("m1")
        with pytest.raises(IntegrityError), transaction.atomic():
            make_message("m1")


class TestLmEmailEvent:
    def test_bounces_and_for_recipient(self):
        msg = make_message("m1")
        make_event("e1", msg, "message.delivered", "a@example.com")
        make_event("e2", msg, "message.hard_bounced", "b@example.com")

        assert list(LmEmailEvent.objects.bounces().values_list("event_id", flat=True)) == ["e2"]
        assert LmEmailEvent.objects.for_recipient("B@EXAMPLE.COM").get().event_id == "e2"
        assert msg.events.count() == 2

    def test_event_survives_message_deletion(self):
        msg = make_message("m1")
        make_event("e1", msg, "message.delivered")
        msg.delete()

        event = LmEmailEvent.objects.get()
        assert event.email_message is None
        assert event.message_id == "m1"

    def test_str_status_and_is_bounce(self):
        event = LmEmailEvent(
            event_id="e1",
            message_id="m1",
            event="message.hard_bounced",
            recipient="r@example.com",
            occurred_at=timezone.now(),
        )
        assert str(event) == "message.hard_bounced m1 r@example.com"
        assert event.status == "hard_bounced"
        assert event.is_bounce is True

        other = LmEmailEvent(event_id="e2", message_id="m1", event="message.auto_replied", occurred_at=timezone.now())
        assert other.status is None
        assert other.is_bounce is False


class TestAdmin:
    def test_models_are_registered_read_only(self):
        for model in (LmEmailMessage, LmEmailEvent):
            model_admin = admin.site._registry[model]
            assert model_admin.check() == []
            assert model_admin.has_add_permission(None) is False
            assert model_admin.has_change_permission(None) is False
