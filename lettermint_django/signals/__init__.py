"""Django signals emitted when a Lettermint webhook event is stored.

One module per signal. All signals are sent with ``sender=LmEmailEvent`` and
these keyword arguments:

- ``event``: the stored :class:`~lettermint_django.models.LmEmailEvent`
- ``email_message``: the matching :class:`~lettermint_django.models.LmEmailMessage`,
  or ``None`` when the event belongs to a message that was not sent through
  this application.

Receivers are called synchronously from the webhook request. Exceptions raised
by receivers are logged, never propagated, so a broken receiver cannot cause
Lettermint to retry the delivery.

Example::

    from django.dispatch import receiver
    from lettermint_django.signals import lm_email_bounced

    @receiver(lm_email_bounced)
    def on_bounce(sender, event, email_message, **kwargs):
        print(event.recipient, event.reason_code)
"""

from .lm_email_bounced import lm_email_bounced
from .lm_email_delivered import lm_email_delivered
from .lm_email_event import lm_email_event
from .lm_email_failed import lm_email_failed

__all__ = ["lm_email_bounced", "lm_email_delivered", "lm_email_event", "lm_email_failed"]
