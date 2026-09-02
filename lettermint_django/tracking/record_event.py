"""``record_event()``: store a verified webhook payload as an ``LmEmailEvent``."""

from collections.abc import Mapping
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .emit_signals import emit_signals
from .enabled import is_tracking_enabled


def record_event(payload):
    """Store a verified webhook payload as an ``LmEmailEvent``.

    Returns ``(event, created)``. ``(None, False)`` means the payload was
    ignored: tracking is disabled, or the payload is not a message event.
    Duplicate deliveries (same event id) return the existing event with
    ``created=False`` and do not emit signals again.

    Database errors propagate so the view returns a 5xx and Lettermint retries.
    """
    if not is_tracking_enabled() or not isinstance(payload, Mapping):
        return None, False

    event_type = payload.get("event")
    event_id = payload.get("id")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        data = {}
    message_id = data.get("message_id")
    if not isinstance(event_type, str) or event_id is None or not message_id:
        return None, False

    from ..models import LmEmailEvent, LmEmailMessage

    response = data.get("response")
    if not isinstance(response, Mapping):
        response = {}
    reason = data.get("reason") or response.get("content") or ""
    reason_code = data.get("reason_code") or response.get("enhanced_status_code") or ""

    with transaction.atomic():
        email_message = (
            LmEmailMessage.objects.select_for_update().filter(message_id=str(message_id)).first()
        )
        event, created = LmEmailEvent.objects.get_or_create(
            event_id=str(event_id),
            defaults={
                "email_message": email_message,
                "message_id": str(message_id),
                "event": event_type,
                "recipient": str(data.get("recipient") or ""),
                "reason": str(reason),
                "reason_code": str(reason_code)[:64],
                "data": dict(data),
                "occurred_at": _parse_timestamp(payload.get("timestamp")),
            },
        )
        if created and email_message is not None:
            _apply_status(email_message, event)

    if created:
        emit_signals(event)
    return event, created


def _apply_status(email_message, event):
    status = event.status
    if status is None:
        return
    changed_at = email_message.status_changed_at
    if changed_at is not None and event.occurred_at < changed_at:
        # Webhooks can arrive out of order (retries); keep the most recent status.
        return
    email_message.status = status
    email_message.status_changed_at = event.occurred_at
    email_message.save(update_fields=["status", "status_changed_at"])


def _parse_timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=dt_timezone.utc)
    if isinstance(value, str):
        try:
            parsed = parse_datetime(value)
        except ValueError:
            parsed = None
        if parsed is not None:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, dt_timezone.utc)
            return parsed
    return timezone.now()
