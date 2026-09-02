"""Status choices and the webhook event to status mapping shared by the models."""

from django.db import models


class LmMessageStatus(models.TextChoices):
    """Lettermint message statuses, mirroring the SDK's ``MessageStatus``."""

    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    SUPPRESSED = "suppressed", "Suppressed"
    PROCESSED = "processed", "Processed"
    DELIVERED = "delivered", "Delivered"
    OPENED = "opened", "Opened"
    CLICKED = "clicked", "Clicked"
    SOFT_BOUNCED = "soft_bounced", "Soft bounced"
    HARD_BOUNCED = "hard_bounced", "Hard bounced"
    SPAM_COMPLAINT = "spam_complaint", "Spam complaint"
    FAILED = "failed", "Failed"
    BLOCKED = "blocked", "Blocked"
    POLICY_REJECTED = "policy_rejected", "Policy rejected"
    UNSUBSCRIBED = "unsubscribed", "Unsubscribed"


BOUNCE_STATUSES = (LmMessageStatus.SOFT_BOUNCED, LmMessageStatus.HARD_BOUNCED)
BOUNCE_EVENTS = ("message.soft_bounced", "message.hard_bounced")

#: Webhook event type -> message status it moves the message to.
#: Events not listed here are stored but do not change the message status.
EVENT_STATUS_MAP = {
    "message.created": LmMessageStatus.QUEUED,
    "message.sent": LmMessageStatus.PROCESSED,
    "message.delivered": LmMessageStatus.DELIVERED,
    "message.soft_bounced": LmMessageStatus.SOFT_BOUNCED,
    "message.hard_bounced": LmMessageStatus.HARD_BOUNCED,
    "message.spam_complaint": LmMessageStatus.SPAM_COMPLAINT,
    "message.failed": LmMessageStatus.FAILED,
    "message.suppressed": LmMessageStatus.SUPPRESSED,
    "message.policy_rejected": LmMessageStatus.POLICY_REJECTED,
    "message.unsubscribed": LmMessageStatus.UNSUBSCRIBED,
    "message.opened": LmMessageStatus.OPENED,
    "message.clicked": LmMessageStatus.CLICKED,
}
