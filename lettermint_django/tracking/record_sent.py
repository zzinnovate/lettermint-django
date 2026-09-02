"""``record_sent()``: store a sent Django email as an ``LmEmailMessage``."""

import logging
from collections.abc import Mapping

from django.db import transaction

from .enabled import is_tracking_enabled

logger = logging.getLogger("lettermint_django")


def record_sent(email_message, response, *, from_email="", route=None):
    """Store a sent Django ``EmailMessage`` as an ``LmEmailMessage``.

    ``response`` is the dict returned by the Lettermint SDK's ``send()``.
    Never raises: a tracking failure must not turn a sent email into an error.
    Returns the created instance, or ``None`` when nothing was stored.
    """
    if not is_tracking_enabled():
        return None

    message_id = _extract_message_id(response)
    if not message_id:
        logger.warning("Lettermint response has no message_id; message not tracked: %r", response)
        return None

    try:
        from ..models import LmEmailMessage, LmMessageStatus

        status = response.get("status")
        if status not in LmMessageStatus.values:
            status = LmMessageStatus.PENDING

        # Savepoint: a failed insert must not poison a caller's outer transaction.
        with transaction.atomic():
            return LmEmailMessage.objects.create(
                message_id=message_id,
                from_email=from_email or email_message.from_email or "",
                to=list(email_message.to or []),
                cc=list(email_message.cc or []),
                bcc=list(email_message.bcc or []),
                subject=email_message.subject or "",
                route=route or "",
                status=status,
            )
    except Exception:
        logger.exception("Failed to record sent Lettermint message %s", message_id)
        return None


def _extract_message_id(response):
    if not isinstance(response, Mapping):
        return None
    message_id = response.get("message_id")
    if isinstance(message_id, str) and message_id.strip():
        return message_id.strip()
    return None
