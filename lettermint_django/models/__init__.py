"""Tracking models for emails sent through Lettermint and their webhook events.

One module per model. These models exist only when ``lettermint_django`` is in
``INSTALLED_APPS``; the email backend never imports this package at import
time, so backend-only installations keep working without migrations.
"""

from .choices import BOUNCE_EVENTS, BOUNCE_STATUSES, EVENT_STATUS_MAP, LmMessageStatus
from .lm_email_event import LmEmailEvent, LmEmailEventQuerySet
from .lm_email_message import LmEmailMessage, LmEmailMessageQuerySet

__all__ = [
    "BOUNCE_EVENTS",
    "BOUNCE_STATUSES",
    "EVENT_STATUS_MAP",
    "LmEmailEvent",
    "LmEmailEventQuerySet",
    "LmEmailMessage",
    "LmEmailMessageQuerySet",
    "LmMessageStatus",
]
