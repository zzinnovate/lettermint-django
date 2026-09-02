"""Django email backend for Lettermint."""

from __future__ import annotations

import base64
from collections.abc import Iterable, Iterator, Mapping, Sequence
from email.utils import formataddr, parseaddr
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

from .tracking import record_sent

if TYPE_CHECKING:
    from lettermint.types import SendMailRequest, SendMailResponse

ROUTE_HEADER = "X-Lettermint-Route"
TAG_HEADER = "X-Lettermint-Tag"


class LettermintEmailBackend(BaseEmailBackend):
    """Send Django EmailMessage objects through the Lettermint API.

    Configuration via Django settings:

        EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
        LETTERMINT_API_KEY = "lm_..."         # required
        LETTERMINT_BASE_URL = "..."           # optional, overrides SDK default
        LETTERMINT_ROUTE = "my-route"         # optional, default route for all emails
        LETTERMINT_TIMEOUT = 30               # optional, request timeout in seconds

    Per-message overrides via extra_headers:

        email.extra_headers["X-Lettermint-Route"] = "transactional"
        email.extra_headers["X-Lettermint-Tag"] = "welcome-campaign"

    When "lettermint_django" is in INSTALLED_APPS, every sent message is stored
    as an LmEmailMessage so webhook events can be matched to it later.

    Bulk sending goes through ``lettermint_django.bulk.send_bulk``, which uses
    :meth:`build_payload` and :meth:`send_payloads` to hit the batch endpoint.
    """

    def __init__(self, *args, **kwargs):
        api_token = self._coerce_str(kwargs.pop("api_token", None) or getattr(settings, "LETTERMINT_API_KEY", None))
        base_url = self._coerce_str(kwargs.pop("base_url", None) or getattr(settings, "LETTERMINT_BASE_URL", None))
        route = self._coerce_str(kwargs.pop("route", None) or getattr(settings, "LETTERMINT_ROUTE", None))
        timeout = kwargs.pop("timeout", None) or getattr(settings, "LETTERMINT_TIMEOUT", None)

        self.api_token = api_token
        self.base_url = base_url
        self.route = route
        self.timeout = timeout
        self.connection = None
        super().__init__(*args, **kwargs)

    def open(self):
        """Open the Lettermint client connection."""
        if self.connection is not None:
            return False

        if not self.api_token:
            if self.fail_silently:
                return False
            raise ImproperlyConfigured(
                "LETTERMINT_API_KEY must be set when using LettermintEmailBackend."
            )

        try:
            from lettermint import Lettermint
        except ImportError as exc:
            if self.fail_silently:
                return False
            raise ImproperlyConfigured(
                "The 'lettermint' package is not installed. Run: pip install lettermint"
            ) from exc

        client_kwargs: dict[str, Any] = {"api_token": self.api_token}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        if self.timeout is not None:
            client_kwargs["timeout"] = float(self.timeout)

        self.connection = Lettermint(**client_kwargs)
        return True

    def close(self):
        """Close the Lettermint client connection."""
        if self.connection is None:
            return
        close_method = getattr(self.connection, "close", None)
        if callable(close_method):
            close_method()
        self.connection = None

    def send_messages(self, email_messages: Iterable[EmailMessage]) -> int:
        """Send Django EmailMessage objects via Lettermint, one request each.

        Django's standard entry point (``send_mail``, ``EmailMessage.send``).
        Returns the number sent. For many messages use
        ``lettermint_django.bulk.send_bulk``, which batches them.
        """
        if not email_messages:
            return 0

        if self.connection is None and self.open() is False:
            return 0

        sent = 0
        for message in email_messages:
            try:
                if self.send_single(message) is not None:
                    sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    def send_single(self, email_message: EmailMessage) -> SendMailResponse | None:
        """Send one Django EmailMessage via the single-send endpoint.

        Returns Lettermint's response (``message_id``, ``status``), or ``None``
        when the message has no recipients or the connection is not open. SDK
        errors propagate. With tracking installed the message is recorded as
        an ``LmEmailMessage``.
        """
        if not email_message.recipients():
            return None

        if self.connection is None:
            return None

        payload = self.build_payload(email_message)
        mail = self._apply_payload(self.connection.email, payload)
        response = mail.send()
        record_sent(payload, response)
        return response

    # Kept for backwards compatibility with 0.3.x.
    _send = send_single

    def send_payloads(self, payloads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """POST a list of payload dicts to the batch endpoint in one request.

        Returns the list of per-message response dicts (``message_id``,
        ``status``) in the same order as ``payloads``. No chunking and no
        checks against Lettermint's limits happen here: whatever Lettermint
        rejects comes back as the SDK's exception. Nothing is recorded here,
        that is the caller's job.
        """
        if not payloads:
            return []
        if self.connection is None and self.open() is False:
            raise ImproperlyConfigured("Lettermint connection could not be opened.")
        return self.connection.email.send_batch(list(payloads))

    def build_payload(self, email_message: EmailMessage) -> SendMailRequest:
        """Translate a Django EmailMessage into the dict Lettermint's send API accepts.

        Keys: ``from``, ``to``, ``cc``, ``bcc``, ``reply_to``, ``route``,
        ``subject``, ``text``, ``html``, ``headers``, ``tag`` and base64
        ``attachments``. The same dict feeds the single-send builder and the
        batch endpoint, so both paths produce identical messages, and a
        subclass overriding ``_get_passthrough_headers()`` affects both.

        Needs no API key or open connection, and the result is plain JSON: build
        payloads where the data lives, store them, and send them elsewhere
        with ``lettermint_django.bulk.send_bulk``. Raises ``ImproperlyConfigured``
        for an invalid sender address.
        """
        sender = self._normalize_address(email_message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload: dict[str, Any] = {"from": sender}

        if email_message.to:
            payload["to"] = list(email_message.to)
        if email_message.cc:
            payload["cc"] = list(email_message.cc)
        if email_message.bcc:
            payload["bcc"] = list(email_message.bcc)

        reply_to = list(getattr(email_message, "reply_to", None) or [])
        if reply_to:
            payload["reply_to"] = [reply_to[0]]

        route = self._resolve_route(email_message)
        if route:
            payload["route"] = route

        payload["subject"] = email_message.subject or ""

        if email_message.body:
            payload["text"] = email_message.body

        html_body = self._get_html_body(email_message)
        if html_body:
            payload["html"] = html_body

        passthrough_headers = self._get_passthrough_headers(email_message)
        if passthrough_headers:
            payload["headers"] = passthrough_headers

        tag = self._resolve_tag(email_message)
        if tag:
            payload["tag"] = tag

        attachments = [
            {"filename": filename, "content": base64.b64encode(raw_content).decode("ascii")}
            for filename, raw_content in self._iter_attachments(email_message)
        ]
        if attachments:
            payload["attachments"] = attachments

        return payload

    @staticmethod
    def _apply_payload(mail: Any, payload: Mapping[str, Any]) -> Any:
        """Feed a payload dict into the SDK's fluent email builder."""
        mail = mail.from_(payload["from"])
        if "to" in payload:
            mail = mail.to(*payload["to"])
        if "cc" in payload:
            mail = mail.cc(*payload["cc"])
        if "bcc" in payload:
            mail = mail.bcc(*payload["bcc"])
        if "reply_to" in payload:
            mail = mail.reply_to(*payload["reply_to"])
        if "route" in payload:
            mail = mail.route(payload["route"])
        mail = mail.subject(payload["subject"])
        if "text" in payload:
            mail = mail.text(payload["text"])
        if "html" in payload:
            mail = mail.html(payload["html"])
        if "headers" in payload:
            mail = mail.headers(payload["headers"])
        if "tag" in payload:
            mail = mail.tag(payload["tag"])
        for attachment in payload.get("attachments", []):
            mail = mail.attach(attachment["filename"], attachment["content"])
        return mail

    def _resolve_route(self, email_message: EmailMessage) -> str | None:
        """Resolve route: per-message header takes priority over backend default."""
        extra_headers = email_message.extra_headers or {}
        route_header = str(extra_headers.get(ROUTE_HEADER, "")).strip()
        return route_header or self.route or None

    @staticmethod
    def _resolve_tag(email_message: EmailMessage) -> str | None:
        """Per-message tag from the X-Lettermint-Tag header, or None."""
        extra_headers = email_message.extra_headers or {}
        return str(extra_headers.get(TAG_HEADER, "")).strip() or None

    def _get_passthrough_headers(self, email_message: EmailMessage) -> dict[str, str]:
        """Return extra headers minus the lettermint-specific ones."""
        if not email_message.extra_headers:
            return {}
        headers = dict(email_message.extra_headers)
        headers.pop(ROUTE_HEADER, None)
        headers.pop(TAG_HEADER, None)
        return headers

    @staticmethod
    def _coerce_str(value):
        """Strip whitespace from string settings and return None if empty."""
        if isinstance(value, str):
            return value.strip() or None
        return value

    @staticmethod
    def _normalize_address(address: Any) -> str:
        """Return a normalized 'Display Name <email>' address string."""
        display_name, email_address = parseaddr(str(address or ""))
        email_address = email_address.strip()
        if not email_address or "@" not in email_address:
            raise ImproperlyConfigured(
                f"Invalid sender address: {address!r}. "
                "DEFAULT_FROM_EMAIL must contain a valid email address."
            )
        display_name = (display_name or "").strip()
        if display_name:
            return formataddr((display_name, email_address))
        return email_address

    @staticmethod
    def _get_html_body(email_message: EmailMessage) -> str:
        """Extract HTML body from EmailMultiAlternatives alternatives."""
        for content, mimetype in getattr(email_message, "alternatives", []):
            if mimetype == "text/html":
                return content
        return ""

    @staticmethod
    def _iter_attachments(email_message: EmailMessage) -> Iterator[tuple[str, bytes]]:
        """Yield (filename, raw_bytes) for each attachment."""
        for attachment in email_message.attachments:
            if isinstance(attachment, tuple):
                filename, content, _ = attachment
            else:
                filename = getattr(attachment, "name", "attachment")
                content = attachment.read() if hasattr(attachment, "read") else attachment

            if isinstance(content, str):
                content = content.encode()

            yield filename or "attachment", content
