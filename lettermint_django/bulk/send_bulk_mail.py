"""``send_bulk_mail()``: render one templated mail per recipient and send it in batches."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from django.http import HttpRequest

from .bulk_result import BulkResult
from .render_bulk_mail import render_bulk_mail
from .send_bulk import send_bulk

if TYPE_CHECKING:
    from ..backend import LettermintEmailBackend


def send_bulk_mail(
    recipients: Iterable[str | Mapping[str, Any]],
    subject: str,
    *,
    text: str | None = None,
    html: str | None = None,
    text_template: str | None = None,
    html_template: str | None = None,
    context: Mapping[str, Any] | None = None,
    from_email: str | None = None,
    reply_to: str | Iterable[str] | None = None,
    route: str | None = None,
    tag: str | None = None,
    headers: Mapping[str, str] | None = None,
    request: HttpRequest | None = None,
    language: str | None = None,
    connection: LettermintEmailBackend | None = None,
    batch_size: int | None = None,
    bulk_id: str | None = None,
) -> BulkResult:
    """Render one mail per recipient with Django templates and send them in batches.

    The Lettermint counterpart of Django's ``send_mass_mail``. Every recipient
    gets their own message and their own ``message_id``; recipients never see
    each other.

    Same mail to everyone::

        send_bulk_mail(
            ["ann@example.com", "bob@example.com"],
            "Doors open at 19:00",
            text_template="emails/doors.txt",
            html_template="emails/doors.html",
            context={"event": event},
            tag="doors-2026",
        )

    A unique mail per person. Every key of a mapping is template context;
    ``email`` is required, ``name`` sets the display name, ``language`` the
    translation for that recipient::

        send_bulk_mail(
            [{"email": g.email, "name": g.first_name, "link": g.invite_url} for g in guests],
            "{{ name }}, you are invited to {{ event.title }}",
            text_template="emails/invite.txt",
            html_template="emails/invite.html",
            context={"event": event},
            tag=f"invite-{event.pk}",
        )

    Args:
        recipients: Addresses, or mappings with an ``email`` key plus template
            variables. Per-recipient keys override ``context``. All recipients
            are validated before anything is rendered or sent.
        subject: Template *string*, rendered per recipient without
            autoescaping and collapsed to one line.
        text: Template *string* for the plain-text body, rendered without
            autoescaping.
        html: Template *string* for the HTML body (autoescaped).
        text_template: Template *name* for the plain-text body, rendered like
            ``render_to_string``; wrap the file in ``{% autoescape off %}``
            as usual.
        html_template: Template *name* for the HTML body.
        context: Shared template context. The templates also get ``email``,
            ``name`` and ``recipient`` (the entry passed in).
        from_email: Sender; defaults to ``DEFAULT_FROM_EMAIL``.
        reply_to: One address or several.
        route: Lettermint route, sent as the ``X-Lettermint-Route`` header.
        tag: Lettermint tag (a campaign name, say), sent as
            ``X-Lettermint-Tag`` and stored on ``LmEmailMessage.tag``.
        headers: Extra email headers, copied per message.
        request: Passed to template rendering so context processors work.
        language: Default language code; a recipient's ``language`` key wins.
        connection: A ``LettermintEmailBackend``; defaults to ``get_connection()``.
        batch_size: Messages per request; defaults to ``LETTERMINT_BATCH_SIZE`` (500).
        bulk_id: Identifier for this send; generated when omitted. See
            :func:`send_bulk`.

    Returns:
        A :class:`BulkResult`. ``item.recipient`` is the entry you passed in,
        so results map straight back to your own rows: store
        ``item.message_id`` there and ``result.bulk_id`` on the thing you sent
        for, then follow up later with
        ``LmEmailMessage.objects.from_bulk(bulk_id)``.

    Raises:
        ValueError: No body template given, or a recipient without a valid
            address. Raised before anything is sent.
        TypeError: A recipient that is neither a string nor a mapping.

    Messages that Lettermint rejects never raise; see ``result.failed`` and
    ``item.reason``. Nothing is retried.
    """
    messages = render_bulk_mail(
        recipients,
        subject,
        text=text,
        html=html,
        text_template=text_template,
        html_template=html_template,
        context=context,
        from_email=from_email,
        reply_to=reply_to,
        route=route,
        tag=tag,
        headers=headers,
        request=request,
        language=language,
    )
    return send_bulk(messages, connection=connection, batch_size=batch_size, bulk_id=bulk_id)
