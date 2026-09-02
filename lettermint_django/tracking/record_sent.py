"""``record_sent()``: store an accepted Lettermint payload as an ``LmEmailMessage``."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

from django.db import transaction

from .enabled import is_tracking_enabled

if TYPE_CHECKING:
    from ..models import LmEmailMessage

logger = logging.getLogger("lettermint_django")


def record_sent(
    payload: Mapping[str, object], response: Mapping[str, object], *, bulk_id: str | None = None
) -> LmEmailMessage | None:
    """Store a sent message as an ``LmEmailMessage``.

    ``payload`` is the dict that was sent to Lettermint (see
    ``LettermintEmailBackend.build_payload``), ``response`` the dict Lettermint
    returned for it; ``bulk_id`` marks the ``send_bulk`` call it belonged to. Never raises: a tracking failure must not turn a sent
    email into an error. Returns the created instance, or ``None``.
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
                from_email=str(payload.get("from") or ""),
                to=list(payload.get("to") or []),
                cc=list(payload.get("cc") or []),
                bcc=list(payload.get("bcc") or []),
                subject=str(payload.get("subject") or ""),
                route=str(payload.get("route") or ""),
                tag=str(payload.get("tag") or ""),
                bulk_id=str(bulk_id or ""),
                status=status,
            )
    except Exception:
        logger.exception("Failed to record sent Lettermint message %s", message_id)
        return None


def _extract_message_id(response: object) -> str | None:
    if not isinstance(response, Mapping):
        return None
    message_id = response.get("message_id")
    if isinstance(message_id, str) and message_id.strip():
        return message_id.strip()
    return None
