"""Read-only Django admin for tracked emails and their events. One module per admin class."""

from .lm_email_event import LmEmailEventAdmin, LmEmailEventInline
from .lm_email_message import LmEmailMessageAdmin

__all__ = ["LmEmailEventAdmin", "LmEmailEventInline", "LmEmailMessageAdmin"]
