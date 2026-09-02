"""``LmEmailMessage``: an email accepted by Lettermint, sent through this backend."""

from __future__ import annotations

from typing import Self

from django.db import models

from .choices import BOUNCE_STATUSES, DELIVERED_STATUSES, LmMessageStatus


class LmEmailMessageQuerySet(models.QuerySet):
    """Filters for tracked messages. ``status`` follows the latest webhook event."""

    def delivered(self) -> Self:
        """Reached the recipient: status ``delivered``, ``opened`` or ``clicked``."""
        return self.filter(status__in=DELIVERED_STATUSES)

    def bounced(self) -> Self:
        """Soft or hard bounced. The SMTP reason is on ``message.events`` (``reason``, ``reason_code``)."""
        return self.filter(status__in=BOUNCE_STATUSES)

    def failed(self) -> Self:
        """Status ``failed``: Lettermint could not send it. The reason is on the event."""
        return self.filter(status=LmMessageStatus.FAILED)

    def not_delivered(self) -> Self:
        """No delivery confirmation: bounced, failed, suppressed, or still in transit.

        In transit means ``pending``, ``queued`` or ``processed``: a delivery event
        may still arrive. Combine with ``created_at`` before treating those as lost.
        """
        return self.exclude(status__in=DELIVERED_STATUSES)

    def not_opened(self) -> Self:
        """Delivered, but no open or click registered.

        A hint, not proof. Open tracking needs the recipient to load images and is
        defeated by mail privacy features. It also requires the ``message.opened``
        event on your Lettermint webhook and open tracking enabled for the message.
        """
        return self.filter(status=LmMessageStatus.DELIVERED)

    def tagged(self, tag: str) -> Self:
        """Messages sent with this ``X-Lettermint-Tag`` (for example a campaign name)."""
        return self.filter(tag=tag)

    def from_bulk(self, bulk_id: str | None) -> Self:
        """Messages accepted in one ``send_bulk`` / ``send_bulk_mail`` call.

        ``bulk_id`` is ``result.bulk_id`` from that call, or the value you passed
        as ``bulk_id=``. Empty or ``None`` matches nothing: single sends carry no
        bulk id. Typical follow-up::

            sent = LmEmailMessage.objects.from_bulk(guestlist.bulk_id)
            ids = sent.bounced().values("message_id")
            # resend from your own rows, keyed on the message_id you stored there
        """
        if not bulk_id:
            return self.none()
        return self.filter(bulk_id=bulk_id)

    def get_status(self, message_id: str) -> str | None:
        """Current status for a Lettermint message id, or ``None`` if not tracked."""
        return self.filter(message_id=message_id).values_list("status", flat=True).first()


class LmEmailMessage(models.Model):
    """An email accepted by Lettermint, sent through :class:`~lettermint_django.LettermintEmailBackend`.

    Created on send, single or bulk, when the tracking app is installed.
    ``status`` and ``status_changed_at`` follow the webhook events in ``events``.
    ``tag`` is the Lettermint tag; ``bulk_id`` groups the messages of one
    ``send_bulk`` call. Bodies, headers and attachments are not stored: resend
    from your own data, joined on ``message_id``.
    """

    message_id = models.CharField(max_length=64, unique=True, help_text="Lettermint message id.")
    from_email = models.CharField(max_length=254)
    to = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    bcc = models.JSONField(default=list, blank=True)
    subject = models.TextField(blank=True)
    route = models.CharField(max_length=100, blank=True)
    tag = models.CharField(max_length=100, blank=True, db_index=True, help_text="Lettermint tag, e.g. a campaign name.")
    bulk_id = models.CharField(
        max_length=64, blank=True, db_index=True, help_text="Id of the send_bulk call this message was part of; empty for single sends."
    )
    status = models.CharField(
        max_length=32, choices=LmMessageStatus.choices, default=LmMessageStatus.PENDING
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LmEmailMessageQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lettermint email message"
        verbose_name_plural = "Lettermint email messages"
        indexes = [models.Index(fields=["status", "created_at"], name="lm_message_status_created_idx")]

    def __str__(self) -> str:
        return f"{self.message_id} ({self.status})"

    @property
    def bounced(self) -> bool:
        """True for a soft or hard bounce."""
        return self.status in BOUNCE_STATUSES
