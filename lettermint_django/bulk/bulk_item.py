"""``BulkItem``: the outcome for one message in a bulk send."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.mail import EmailMessage


@dataclass
class BulkItem:
    """Outcome for a single message of a ``send_bulk`` call.

    Attributes:
        payload: The dict that was (or would have been) sent to Lettermint.
        email_message: The Django message it was built from, or ``None`` when a
            payload dict was passed to ``send_bulk`` directly.
        message_id: Lettermint's id for the message, when accepted. Store it on
            your own row to join webhook events and tracking rows back later.
        status: Lettermint's initial status, when accepted.
        error: The exception that stopped the message, else ``None``.
        response: Lettermint's raw response for this message, when accepted.

    ``ok`` says whether Lettermint accepted it; ``reason`` explains a failure in
    Lettermint's own words (HTTP status and response body included).
    """

    payload: dict[str, Any] | None = None
    email_message: EmailMessage | None = None
    message_id: str | None = None
    status: str | None = None
    error: Exception | None = None
    response: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        """True when Lettermint accepted the message and returned a ``message_id``."""
        return self.error is None and bool(self.message_id)

    @property
    def reason(self) -> str:
        """Why the message was not accepted, in Lettermint's own words where available.

        Empty for accepted messages. For SDK errors this includes the HTTP status
        and Lettermint's response body verbatim; nothing is interpreted.
        """
        if self.error is None:
            return ""
        text = str(self.error) or type(self.error).__name__
        status_code = getattr(self.error, "status_code", None)
        if status_code and str(status_code) not in text:
            text = f"HTTP {status_code}: {text}"
        body = getattr(self.error, "response_body", None)
        if body:
            text = f"{text} {body}"
        return text

    @property
    def to(self) -> list[str]:
        """The addresses in ``to``, without ``cc`` and ``bcc``.

        Who the message was for. Use this, not :attr:`recipients`, to check
        that an outcome belongs to the person you meant: a copy address would
        satisfy that check just as happily.
        """
        return list((self.payload or {}).get("to") or [])

    @property
    def recipients(self) -> list[str]:
        """All addresses in ``to``, ``cc`` and ``bcc`` of the payload."""
        payload = self.payload or {}
        return [*(payload.get("to") or []), *(payload.get("cc") or []), *(payload.get("bcc") or [])]

    @property
    def recipient(self) -> Any:
        """The entry passed to ``render_bulk_mail`` / ``send_bulk_mail`` for this message.

        That is the address string or the mapping you supplied, so it maps straight
        back to your own data. Falls back to the first ``to`` address when the
        message was not rendered by this package (a payload dict, or your own
        ``EmailMessage``).
        """
        original = getattr(self.email_message, "lm_recipient", None)
        if original is not None:
            return original
        to = list((self.payload or {}).get("to") or [])
        return to[0] if to else None
