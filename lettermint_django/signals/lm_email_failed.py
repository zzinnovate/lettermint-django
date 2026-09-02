"""``lm_email_failed``: sent for ``message.failed``."""

from django.dispatch import Signal

lm_email_failed = Signal()
