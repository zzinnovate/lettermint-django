"""Bulk sending through Lettermint's batch endpoint. One module per function.

Two entry points:

- :func:`send_bulk` sends any iterable of Django ``EmailMessage`` objects or
  prepared payload dicts in batches (500 per request by default) and returns
  per-message results.
- :func:`send_bulk_mail` first renders one personalised message per recipient
  from templates (via :func:`render_bulk_mail`) and then calls ``send_bulk``.

Both return a :class:`BulkResult` of :class:`BulkItem` objects: per message
whether Lettermint accepted it (``message_id``) or why not (``reason``).
Nothing is retried. With the tracking app installed, every accepted message
becomes an ``LmEmailMessage`` carrying ``result.bulk_id``, so a send can be
followed up later with ``LmEmailMessage.objects.from_bulk(bulk_id)`` and its
``bounced()``, ``not_delivered()`` and ``not_opened()`` filters. Bodies are
not stored; resend from your own data, keyed on the ``message_id`` you keep.
"""

from .bulk_item import BulkItem
from .bulk_result import BulkResult
from .render_bulk_mail import render_bulk_mail
from .send_bulk import send_bulk
from .send_bulk_mail import send_bulk_mail

__all__ = ["BulkItem", "BulkResult", "render_bulk_mail", "send_bulk", "send_bulk_mail"]
