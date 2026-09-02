"""``LmEmailEvent``: a webhook event received from Lettermint for a message."""

from django.db import models

from .choices import BOUNCE_EVENTS, EVENT_STATUS_MAP
from .lm_email_message import LmEmailMessage


class LmEmailEventQuerySet(models.QuerySet):
    def for_recipient(self, email):
        return self.filter(recipient__iexact=email)

    def bounces(self):
        return self.filter(event__in=BOUNCE_EVENTS)


class LmEmailEvent(models.Model):
    """A webhook event received from Lettermint for a message."""

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

    def __str__(self):
        return f"{self.event} {self.message_id} {self.recipient}".strip()

    @property
    def status(self):
        """Message status this event maps to, or ``None`` if it does not change status."""
        return EVENT_STATUS_MAP.get(self.event)

    @property
    def is_bounce(self):
        return self.event in BOUNCE_EVENTS
