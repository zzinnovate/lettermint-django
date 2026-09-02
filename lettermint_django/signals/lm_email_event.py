"""``lm_email_event``: sent for every stored ``message.*`` event."""

from django.dispatch import Signal

lm_email_event = Signal()
