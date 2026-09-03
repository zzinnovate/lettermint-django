"""``send_bulk()``: send messages through Lettermint's batch endpoint, in chunks."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Mapping, Sequence
from itertools import islice
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from ..backend import ROUTE_HEADER, TAG_HEADER
from ..tracking import record_sent
from .bulk_item import BulkItem
from .bulk_result import BulkResult

if TYPE_CHECKING:
    from ..backend import LettermintEmailBackend

logger = logging.getLogger("lettermint_django")

#: Assumed number of messages Lettermint accepts per batch request.
#: Lettermint's own documentation is authoritative; override with LETTERMINT_BATCH_SIZE.
DEFAULT_BATCH_SIZE = 500


def get_batch_size(batch_size: int | None = None) -> int:
    """Resolve the chunk size: argument, then ``LETTERMINT_BATCH_SIZE``, then 500."""
    if batch_size is None:
        batch_size = getattr(settings, "LETTERMINT_BATCH_SIZE", None)
    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE
    size = int(batch_size)
    if size < 1:
        raise ValueError("Batch size must be at least 1.")
    return size


def get_bulk_route(route: str | None = None) -> str | None:
    """Resolve the route of a bulk send: argument, then ``LETTERMINT_BULK_ROUTE``, then none.

    ``None`` leaves the routing to the message's own header, else the backend's
    ``LETTERMINT_ROUTE``, else the default route of the API key.
    """
    if route is None:
        route = getattr(settings, "LETTERMINT_BULK_ROUTE", None)
    if isinstance(route, str):
        route = route.strip() or None
    return route


def send_bulk(
    messages: Iterable[EmailMessage | Mapping[str, Any]],
    *,
    connection: LettermintEmailBackend | None = None,
    batch_size: int | None = None,
    bulk_id: str | None = None,
    route: str | None = None,
    tag: str | None = None,
) -> BulkResult:
    """Send many messages through Lettermint's batch endpoint and report per message.

    Args:
        messages: Any iterable of Django ``EmailMessage`` objects, of payload
            dicts as produced by ``LettermintEmailBackend.build_payload()``
            (plain JSON, so they can come out of a queue or blob), or a mix.
            Consumed lazily, ``batch_size`` items at a time: a generator
            renders as batches are pulled, a list is rendered before the first
            request.
        connection: A ``LettermintEmailBackend``. Defaults to
            ``get_connection()``; any other backend raises ``TypeError``.
        batch_size: Messages per request. Defaults to ``LETTERMINT_BATCH_SIZE``
            (500). That default assumes Lettermint's batch limit; check their
            documentation, this package does not enforce it.
        bulk_id: Identifier stored as ``LmEmailMessage.bulk_id`` on every
            accepted message. Generated per call when omitted. Pass your own to
            make several calls count as one send, for example one call per
            worker or serverless invocation.
        route: Lettermint route for this send, overriding the backend's
            ``LETTERMINT_ROUTE``. Defaults to ``LETTERMINT_BULK_ROUTE``. A
            message carrying its own ``X-Lettermint-Route`` header keeps it,
            and so does a prepared payload that already names a route.
        tag: Lettermint tag for this send, stored on ``LmEmailMessage.tag``. A
            message carrying its own ``X-Lettermint-Tag`` header keeps it.

    Returns:
        A :class:`BulkResult` with one :class:`BulkItem` per input, in order:
        ``message_id`` and ``status`` when Lettermint accepted the message,
        ``error`` and ``reason`` (Lettermint's own words) when it did not.
        ``result.bulk_id`` finds the tracked messages again later.

    Behaviour:
        * Every chunk is one request. Nothing is retried: a chunk Lettermint
          rejects fails all its messages with the reason, and the next chunk is
          still sent. To isolate one bad message in a rejected chunk, resend
          those messages yourself with ``send_bulk(failed, batch_size=1)``.
        * A timeout is not a confirmed failure: Lettermint may have accepted the
          batch. Check ``LmEmailMessage`` or your webhook events before resending.
        * A message without recipients, or whose payload cannot be built, is
          reported as failed and never sent.
        * Never raises for individual messages. Configuration errors (missing
          API key, connection cannot be opened, wrong backend) do raise.
        * Synchronous. Run large sends from a background task, not a request.

    Following up, with the tracking app installed::

        result = send_bulk(messages)
        sent = LmEmailMessage.objects.from_bulk(result.bulk_id)
        sent.bounced()        # reason on message.events
        sent.not_delivered()  # bounced, failed, suppressed, or still in transit
        sent.not_opened()     # delivered, no open registered (a hint, not proof)
        # Bodies are not stored: resend from your own data, joined on the
        # message_id you kept per row.
    """
    connection = connection or get_connection()
    if not hasattr(connection, "send_payloads"):
        raise TypeError(
            "send_bulk requires the Lettermint backend; got "
            f"{type(connection).__module__}.{type(connection).__qualname__}."
        )

    result = BulkResult(bulk_id=str(bulk_id or uuid.uuid4().hex))
    chunk_size = get_batch_size(batch_size)
    bulk_route = get_bulk_route(route)
    iterator = iter(messages)
    opened = False
    warned = False

    while True:
        chunk = list(islice(iterator, chunk_size))
        if not chunk:
            break
        if not opened:
            connection.open()
            opened = True

        items = [_prepare(connection, message, bulk_route, tag) for message in chunk]
        result.items.extend(items)

        sendable = [item for item in items if item.error is None]
        if not sendable:
            continue

        payloads = [item.payload for item in sendable]
        if not warned and any("route" not in payload for payload in payloads):
            warned = True
            logger.warning(
                "Bulk send %s has messages with no route: they go out on whichever route is the "
                "default of your API key, which may be the one your transactional mail uses. Set "
                "LETTERMINT_BULK_ROUTE, or pass route=, to send them somewhere else.",
                result.bulk_id,
            )

        try:
            responses = connection.send_payloads(payloads)
        except Exception as exc:
            logger.warning("Lettermint rejected a batch of %d messages: %s", len(payloads), exc)
            for item in sendable:
                item.error = exc
            continue

        _apply_responses(sendable, responses, result.bulk_id)

    return result


def _prepare(
    connection: LettermintEmailBackend,
    message: EmailMessage | Mapping[str, Any],
    route: str | None = None,
    tag: str | None = None,
) -> BulkItem:
    """Turn one input into a BulkItem with a payload, or with the error that prevented it."""
    if isinstance(message, Mapping):
        item = BulkItem(payload=dict(message))
        # A prepared payload was composed deliberately, somewhere else and
        # possibly long ago; only fill in what it left open.
        _apply_send_wide(item.payload, route, tag, asked_for=set(item.payload))
    else:
        item = BulkItem(email_message=message)
        try:
            item.payload = connection.build_payload(message)
        except Exception as exc:
            item.error = exc
            return item
        # build_payload has already written the backend's own route into the
        # payload, so what the message asked for is read from its headers.
        headers = message.extra_headers or {}
        asked_for = {
            key
            for key, header in (("route", ROUTE_HEADER), ("tag", TAG_HEADER))
            if str(headers.get(header, "")).strip()
        }
        _apply_send_wide(item.payload, route, tag, asked_for=asked_for)
    if not item.recipients:
        item.error = ValueError("Message has no recipients.")
    return item


def _apply_send_wide(payload: dict[str, Any], route: str | None, tag: str | None, *, asked_for: set[str]) -> None:
    """Write the send-wide route and tag into a payload that did not ask for its own."""
    for key, value in (("route", route), ("tag", tag)):
        if value and key not in asked_for:
            payload[key] = value


def _apply_responses(items: Sequence[BulkItem], responses: Any, bulk_id: str) -> None:
    responses = list(responses or [])
    if len(responses) != len(items):
        logger.warning("Lettermint returned %d batch responses for %d messages.", len(responses), len(items))
    for index, item in enumerate(items):
        response = responses[index] if index < len(responses) else None
        if not isinstance(response, Mapping) or not response.get("message_id"):
            item.error = RuntimeError(f"Lettermint returned no message_id for this message: {response!r}")
            continue
        item.response = dict(response)
        item.message_id = response.get("message_id")
        item.status = response.get("status")
        record_sent(item.payload, response, bulk_id=bulk_id)
