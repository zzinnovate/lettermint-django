"""Django email backend for Lettermint."""

import base64
from email.utils import formataddr, parseaddr
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class LettermintEmailBackend(BaseEmailBackend):
    """Send Django EmailMessage objects through the Lettermint API.

    Configuration via Django settings:

        EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
        LETTERMINT_API_KEY = "lm_..."         # required
        LETTERMINT_BASE_URL = "..."           # optional, overrides SDK default
        LETTERMINT_ROUTE = "my-route"         # optional, default route for all emails
        LETTERMINT_TIMEOUT = 30               # optional, request timeout in seconds

    Per-message route override via extra_headers:

        email.extra_headers["X-Lettermint-Route"] = "transactional"
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

    def send_messages(self, email_messages):
        """Send a list of Django EmailMessage objects via Lettermint."""
        if not email_messages:
            return 0

        if self.connection is None and self.open() is False:
            return 0

        sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, email_message):
        """Send a single Django EmailMessage via the Lettermint SDK."""
        if not email_message.recipients():
            return False

        if self.connection is None:
            return False

        mail = self.connection.email

        from_email = email_message.from_email or settings.DEFAULT_FROM_EMAIL
        mail = mail.from_(self._normalize_address(from_email))

        if email_message.to:
            mail = mail.to(*email_message.to)
        if email_message.cc:
            mail = mail.cc(*email_message.cc)
        if email_message.bcc:
            mail = mail.bcc(*email_message.bcc)

        reply_to = list(getattr(email_message, "reply_to", None) or [])
        if reply_to:
            mail = mail.reply_to(reply_to[0])

        route = self._resolve_route(email_message)
        if route:
            mail = mail.route(route)

        mail = mail.subject(email_message.subject or "")

        if email_message.body:
            mail = mail.text(email_message.body)

        html_body = self._get_html_body(email_message)
        if html_body:
            mail = mail.html(html_body)

        passthrough_headers = self._get_passthrough_headers(email_message)
        if passthrough_headers:
            mail = mail.headers(passthrough_headers)

        for filename, raw_content in self._iter_attachments(email_message):
            encoded = base64.b64encode(raw_content).decode("ascii")
            mail = mail.attach(filename, encoded)

        mail.send()
        return True

    def _resolve_route(self, email_message):
        """Resolve route: per-message header takes priority over backend default."""
        extra_headers = email_message.extra_headers or {}
        route_header = str(extra_headers.get("X-Lettermint-Route", "")).strip()
        return route_header or self.route or None

    def _get_passthrough_headers(self, email_message):
        """Return extra headers minus the lettermint-specific ones."""
        if not email_message.extra_headers:
            return {}
        headers = dict(email_message.extra_headers)
        headers.pop("X-Lettermint-Route", None)
        return headers

    @staticmethod
    def _coerce_str(value):
        """Strip whitespace from string settings and return None if empty."""
        if isinstance(value, str):
            return value.strip() or None
        return value

    @staticmethod
    def _normalize_address(address):
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
    def _get_html_body(email_message):
        """Extract HTML body from EmailMultiAlternatives alternatives."""
        for content, mimetype in getattr(email_message, "alternatives", []):
            if mimetype == "text/html":
                return content
        return ""

    @staticmethod
    def _iter_attachments(email_message):
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
