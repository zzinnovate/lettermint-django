"""``LmEmailMessage``: an email sent through the Lettermint backend."""

from django.db import models

from .choices import BOUNCE_STATUSES, LmMessageStatus


class LmEmailMessageQuerySet(models.QuerySet):
    def delivered(self):
        return self.filter(status=LmMessageStatus.DELIVERED)

    def bounced(self):
        return self.filter(status__in=BOUNCE_STATUSES)

    def failed(self):
        return self.filter(status=LmMessageStatus.FAILED)

    def get_status(self, message_id):
        """Return the current status for a Lettermint message id, or ``None`` if unknown."""
        return self.filter(message_id=message_id).values_list("status", flat=True).first()


class LmEmailMessage(models.Model):
    """An email that was sent through :class:`~lettermint_django.LettermintEmailBackend`."""

    message_id = models.CharField(max_length=64, unique=True, help_text="Lettermint message id.")
    from_email = models.CharField(max_length=254)
    to = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    bcc = models.JSONField(default=list, blank=True)
    subject = models.TextField(blank=True)
    route = models.CharField(max_length=100, blank=True)
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

    def __str__(self):
        return f"{self.message_id} ({self.status})"

    @property
    def bounced(self):
        return self.status in BOUNCE_STATUSES
