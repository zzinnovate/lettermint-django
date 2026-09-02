"""``lm_email_bounced``: sent for ``message.soft_bounced`` and ``message.hard_bounced``."""

from django.dispatch import Signal

lm_email_bounced = Signal()
