"""``render_bulk_mail()``: build one personalised ``EmailMessage`` per recipient."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from email.utils import formataddr
from typing import Any, NamedTuple

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.http import HttpRequest
from django.template import engines
from django.template.loader import render_to_string
from django.utils import translation

from ..backend import ROUTE_HEADER, TAG_HEADER

#: Recipient keys with a fixed meaning; everything else is template context.
RESERVED_KEYS = ("email", "name", "language")


class _Recipient(NamedTuple):
    original: Any
    email: str
    name: str
    language: str | None
    variables: dict[str, Any]


def render_bulk_mail(
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
) -> Iterator[EmailMessage]:
    """Yield one ``EmailMessage`` per recipient, rendered with Django templates.

    This is the rendering half of :func:`send_bulk_mail`; use it on its own to
    inspect messages, to hand them to :func:`send_bulk` later, or to turn them
    into JSON payloads with ``LettermintEmailBackend.build_payload()``.

    ``recipients`` is an iterable of email addresses or mappings with an
    ``email`` key. Every other key of a mapping is available in the templates,
    on top of the shared ``context``; ``name`` is also used for the display
    name, and ``language`` (a language code) activates that translation while
    rendering that recipient's message. ``email``, ``name`` and ``recipient``
    (the original entry) are always in the context.

    ``subject``, ``text`` and ``html`` are template *strings*; ``text_template``
    and ``html_template`` are template *names* loaded through Django's template
    engines (with ``request`` passed through, so context processors work).
    Subject and ``text`` strings render with autoescaping off; template files
    keep whatever the file declares, exactly like ``render_to_string``.

    Recipients are validated and templates compiled when this function is
    called, so a bad address or missing body raises before anything is sent.
    Rendering itself is lazy: each message is built as the iterator is pulled,
    which is how ``send_bulk`` interleaves rendering with sending.

    Raises:
        ValueError: None of ``text``, ``html``, ``text_template`` or
            ``html_template`` given, or a recipient without a valid address.
        TypeError: A recipient that is neither a string nor a mapping.
    """
    if not any((text, html, text_template, html_template)):
        raise ValueError("render_bulk_mail needs text, html, text_template or html_template.")

    normalized = [_normalize_recipient(recipient) for recipient in recipients]

    django_engine = engines["django"]
    subject_template = django_engine.from_string(_autoescape_off(subject))
    text_string_template = django_engine.from_string(_autoescape_off(text)) if text else None
    html_string_template = django_engine.from_string(html) if html else None

    shared = dict(context or {})
    base_headers = dict(headers or {})
    if route:
        base_headers[ROUTE_HEADER] = route
    if tag:
        base_headers[TAG_HEADER] = tag
    reply_to_list = _as_list(reply_to)

    def render() -> Iterator[EmailMessage]:
        for recipient in normalized:
            render_context = {
                **shared,
                **recipient.variables,
                "email": recipient.email,
                "name": recipient.name,
                "recipient": recipient.original,
            }
            to_address = formataddr((recipient.name, recipient.email)) if recipient.name else recipient.email

            with translation.override(recipient.language or language):
                rendered_subject = _single_line(subject_template.render(render_context, request))
                text_body = ""
                if text_string_template is not None:
                    text_body = text_string_template.render(render_context, request)
                elif text_template:
                    text_body = render_to_string(text_template, render_context, request=request)
                html_body = ""
                if html_string_template is not None:
                    html_body = html_string_template.render(render_context, request)
                elif html_template:
                    html_body = render_to_string(html_template, render_context, request=request)

            message_kwargs: dict[str, Any] = {
                "subject": rendered_subject,
                "body": text_body,
                "from_email": from_email,
                "to": [to_address],
                "reply_to": reply_to_list or None,
                "headers": dict(base_headers) or None,
            }
            if html_body:
                message = EmailMultiAlternatives(**message_kwargs)
                message.attach_alternative(html_body, "text/html")
            else:
                message = EmailMessage(**message_kwargs)
            message.lm_recipient = recipient.original
            yield message

    return render()


def _normalize_recipient(recipient: str | Mapping[str, Any]) -> _Recipient:
    if isinstance(recipient, str):
        email = recipient.strip()
        name = ""
        recipient_language = None
        variables: dict[str, Any] = {}
    elif isinstance(recipient, Mapping):
        email = str(recipient.get("email") or "").strip()
        name = str(recipient.get("name") or "").strip()
        recipient_language = recipient.get("language") or None
        variables = {key: value for key, value in recipient.items() if key not in RESERVED_KEYS}
    else:
        raise TypeError(f"Recipient must be an email address or a mapping with an 'email' key, got {recipient!r}.")
    if not email or "@" not in email:
        raise ValueError(f"Recipient has no valid email address: {recipient!r}.")
    return _Recipient(recipient, email, name, recipient_language, variables)


def _autoescape_off(template_string: str) -> str:
    return "{% autoescape off %}" + str(template_string) + "{% endautoescape %}"


def _single_line(value: str) -> str:
    return " ".join(str(value).split())


def _as_list(value: str | Iterable[str] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)
