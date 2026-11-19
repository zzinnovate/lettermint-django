"""Tests for the lettermint_prune management command and the privacy system checks."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from lettermint_django.checks import check_tracking_retention, check_tracking_settings
from lettermint_django.models import LmEmailEvent, LmEmailMessage


def make_message(message_id, age_days):
    message = LmEmailMessage.objects.create(message_id=message_id, from_email="a@example.com", to=["r@example.com"])
    LmEmailMessage.objects.filter(pk=message.pk).update(created_at=timezone.now() - timedelta(days=age_days))
    return message


def make_event(event_id, age_days, message=None, message_id="msg_elsewhere"):
    return LmEmailEvent.objects.create(
        event_id=event_id,
        email_message=message,
        message_id=message.message_id if message else message_id,
        event="message.delivered",
        occurred_at=timezone.now() - timedelta(days=age_days),
    )


def prune(*args):
    out = StringIO()
    call_command("lettermint_prune", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def rows():
    old = make_message("old", 50)
    new = make_message("new", 5)
    make_event("old_event", 50, old)
    make_event("recent_event_of_old_message", 5, old)
    make_event("new_event", 5, new)
    make_event("old_unknown", 50)
    make_event("new_unknown", 5)


class TestPrune:
    def test_deletes_rows_older_than_the_cutoff(self, rows):
        output = prune("--days", "40")

        assert list(LmEmailMessage.objects.values_list("message_id", flat=True)) == ["new"]
        assert set(LmEmailEvent.objects.values_list("event_id", flat=True)) == {"new_event", "new_unknown"}
        assert "Deleted 1 messages and 3 events older than 40 days." in output

    def test_uses_the_setting(self, rows, settings):
        settings.LETTERMINT_TRACKING_RETENTION_DAYS = 40
        prune()
        assert LmEmailMessage.objects.count() == 1

    def test_days_overrides_the_setting(self, rows, settings):
        settings.LETTERMINT_TRACKING_RETENTION_DAYS = 40
        prune("--days", "60")
        assert LmEmailMessage.objects.count() == 2

    def test_dry_run_deletes_nothing(self, rows):
        output = prune("--days", "40", "--dry-run")
        assert "Would delete 1 messages and 3 events" in output
        assert (LmEmailMessage.objects.count(), LmEmailEvent.objects.count()) == (2, 5)

    def test_without_retention_does_nothing(self, rows):
        assert "No retention set" in prune()
        assert (LmEmailMessage.objects.count(), LmEmailEvent.objects.count()) == (2, 5)

    def test_rejects_days_below_one(self):
        with pytest.raises(CommandError):
            prune("--days", "0")


class TestRetentionCheck:
    def test_warns_without_retention(self):
        assert [w.id for w in check_tracking_retention(None)] == ["lettermint_django.W003"]

    def test_silent_with_retention(self, settings):
        settings.LETTERMINT_TRACKING_RETENTION_DAYS = 40
        assert check_tracking_retention(None) == []

    def test_silent_when_tracking_off(self, settings):
        settings.LETTERMINT_TRACKING = False
        assert check_tracking_retention(None) == []


class TestSettingsCheck:
    def test_defaults_are_valid(self):
        assert check_tracking_settings(None) == []

    @pytest.mark.parametrize(
        "name, value",
        [
            ("LETTERMINT_TRACKING_EVENT_DATA", "partial"),
            ("LETTERMINT_TRACKING_RECIPIENTS", "hash"),
            ("LETTERMINT_TRACKING_RETENTION_DAYS", 0),
            ("LETTERMINT_TRACKING_RETENTION_DAYS", "forty"),
            ("LETTERMINT_TRACKING_RETENTION_DAYS", True),
        ],
    )
    def test_invalid_values_are_errors(self, settings, name, value):
        setattr(settings, name, value)
        errors = check_tracking_settings(None)
        assert [e.id for e in errors] == ["lettermint_django.E001"]
        assert name in errors[0].msg
