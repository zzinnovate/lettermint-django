"""``BulkResult``: the outcome of a bulk send."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .bulk_item import BulkItem


@dataclass
class BulkResult:
    """Per-message outcomes of a ``send_bulk`` or ``send_bulk_mail`` call.

    Attributes:
        items: One :class:`BulkItem` per input message, in input order.
        bulk_id: Identifies this send. With the tracking app installed it is
            stored as ``LmEmailMessage.bulk_id`` on every accepted message, so
            ``LmEmailMessage.objects.from_bulk(result.bulk_id)`` finds them
            again later, with their webhook-updated status. Keep it on the
            object you sent for (an event, a guest list).

    ``bool(result)`` is true only when every message was accepted. A bulk send
    never raises for individual messages; inspect ``failed`` and
    ``item.reason`` instead.

    Example::

        result = send_bulk_mail(recipients, subject, text_template="emails/invite.txt")
        for item in result.failed:
            logger.warning("%s: %s", item.recipient, item.reason)
        guestlist.bulk_id = result.bulk_id
        for item in result.sent:
            item.recipient["guest"].last_message_id = item.message_id
    """

    items: list[BulkItem] = field(default_factory=list)
    bulk_id: str = ""

    @property
    def sent(self) -> list[BulkItem]:
        """Items Lettermint accepted (each has a ``message_id``)."""
        return [item for item in self.items if item.ok]

    @property
    def failed(self) -> list[BulkItem]:
        """Items that did not go out; see ``item.reason`` for Lettermint's explanation."""
        return [item for item in self.items if not item.ok]

    @property
    def sent_count(self) -> int:
        return len(self.sent)

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def message_ids(self) -> list[str]:
        """Lettermint ids of the accepted messages, in input order."""
        return [item.message_id for item in self.sent if item.message_id]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[BulkItem]:
        return iter(self.items)

    def __bool__(self) -> bool:
        return self.failed_count == 0 and self.sent_count > 0
