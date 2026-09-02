"""``emit_signals()``: send the generic and event-specific signals for a stored event."""

import logging

from ..signals import lm_email_bounced, lm_email_delivered, lm_email_event, lm_email_failed

logger = logging.getLogger("lettermint_django")

SIGNALS_BY_EVENT = {
    "message.delivered": lm_email_delivered,
    "message.soft_bounced": lm_email_bounced,
    "message.hard_bounced": lm_email_bounced,
    "message.failed": lm_email_failed,
}


def emit_signals(event):
    """Send ``lm_email_event`` plus the event-specific signal, if any.

    Uses ``send_robust`` so a failing receiver is logged and never propagates
    into the webhook request.
    """
    signals = [lm_email_event]
    specific = SIGNALS_BY_EVENT.get(event.event)
    if specific is not None:
        signals.append(specific)
    for signal in signals:
        results = signal.send_robust(sender=type(event), event=event, email_message=event.email_message)
        for receiver, result in results:
            if isinstance(result, Exception):
                logger.error("Signal receiver %r failed for %s", receiver, event, exc_info=result)
