"""``lm_email_delivered``: sent for ``message.delivered``."""

from django.dispatch import Signal

lm_email_delivered = Signal()
