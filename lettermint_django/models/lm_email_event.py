"""``LmEmailEvent``: a webhook event received from Lettermint for a message."""

from __future__ import annotations

from typing import Self

from django.db import models

from .choices import BOUNCE_EVENTS, EVENT_STATUS_MAP
from .lm_email_message import LmEmailMessage


class LmEmailEventQuerySet(models.QuerySet):
    """Filters for webhook events. One event per recipient per status change."""

    def for_recipient(self, email: str) -> Self:
        """Events about this address (case-insensitive), across all messages."""
        return self.filter(recipient__iexact=email)

    def bounces(self) -> Self:
        """``message.soft_bounced`` and ``message.hard_bounced`` events."""
        return self.filter(event__in=BOUNCE_EVENTS)

    def from_bulk(self, bulk_id: str | None) -> Self:
        """Events for the messages of one ``send_bulk`` call (see ``BulkResult.bulk_id``)."""
        if not bulk_id:
            return self.none()
        return self.filter(email_message__bulk_id=bulk_id)


class LmEmailEvent(models.Model):
    """A webhook event received from Lettermint for a message.

    Stored once per Lettermint event id, so retried deliveries never duplicate.
    ``reason`` and ``reason_code`` hold Lettermint's explanation for bounces and
    failures (the SMTP response and enhanced status code, or ``reason`` /
    ``reason_code`` for ``message.failed``); ``data`` keeps the raw payload.
    ``email_message`` is ``None`` for messages not sent through this app.
    """

    event_id = models.CharField(
        max_length=64, unique=True, help_text="Lettermint webhook event id, used for de-duplication."
    )
    email_message = models.ForeignKey(
        LmEmailMessage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
        help_text="Empty when the message was not sent through this application.",
    )
    message_id = models.CharField(max_length=64, db_index=True, help_text="Lettermint message id.")
    event = models.CharField(
        max_length=64, db_index=True, help_text='Webhook event type, e.g. "message.hard_bounced".'
    )
    recipient = models.CharField(max_length=254, blank=True, db_index=True)
    reason = models.TextField(blank=True, help_text="Human-readable failure or bounce reason.")
    reason_code = models.CharField(
        max_length=64, blank=True, help_text="Machine-readable reason code or enhanced SMTP status code."
    )
    data = models.JSONField(default=dict, blank=True, help_text="Raw 'data' object of the webhook payload.")
    occurred_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LmEmailEventQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "Lettermint email event"
        verbose_name_plural = "Lettermint email events"

    def __str__(self) -> str:
        return f"{self.event} {self.message_id} {self.recipient}".strip()

    @property
    def status(self) -> str | None:
        """Message status this event maps to, or ``None`` if it does not change status."""
        return EVENT_STATUS_MAP.get(self.event)

    @property
    def is_bounce(self) -> bool:
        return self.event in BOUNCE_EVENTS
