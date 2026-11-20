"""Tests for LettermintEmailBackend."""

import pytest
from unittest.mock import MagicMock, patch, call
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives

from lettermint_django import LettermintEmailBackend
from .conftest import sent_payload


class TestLettermintEmailBackendInit:
    def test_reads_api_key_from_settings(self, settings):
        settings.LETTERMINT_API_KEY = "lm_from_settings"
        backend = LettermintEmailBackend()
        assert backend.api_token == "lm_from_settings"

    def test_kwarg_overrides_settings(self, settings):
        settings.LETTERMINT_API_KEY = "lm_from_settings"
        backend = LettermintEmailBackend(api_token="lm_override")
        assert backend.api_token == "lm_override"

    def test_strips_whitespace_from_api_key(self, settings):
        settings.LETTERMINT_API_KEY = "  lm_padded  "
        backend = LettermintEmailBackend()
        assert backend.api_token == "lm_padded"

    def test_empty_string_api_key_becomes_none(self, settings):
        settings.LETTERMINT_API_KEY = "   "
        backend = LettermintEmailBackend()
        assert backend.api_token is None

    def test_reads_base_url_from_settings(self, settings):
        settings.LETTERMINT_BASE_URL = "https://custom.api.com"
        backend = LettermintEmailBackend()
        assert backend.base_url == "https://custom.api.com"

    def test_reads_route_from_settings(self, settings):
        settings.LETTERMINT_ROUTE = "transactional"
        backend = LettermintEmailBackend()
        assert backend.route == "transactional"

    def test_reads_timeout_from_settings(self, settings):
        settings.LETTERMINT_TIMEOUT = 60
        backend = LettermintEmailBackend()
        assert backend.timeout == 60


class TestLettermintEmailBackendOpen:
    def test_raises_when_no_api_key(self, settings):
        settings.LETTERMINT_API_KEY = None
        backend = LettermintEmailBackend()
        with pytest.raises(ImproperlyConfigured, match="LETTERMINT_API_KEY"):
            backend.open()

    def test_returns_false_silently_when_no_api_key(self, settings):
        settings.LETTERMINT_API_KEY = None
        backend = LettermintEmailBackend(fail_silently=True)
        result = backend.open()
        assert result is False

    def test_raises_when_lettermint_not_installed(self, settings):
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        with patch.dict("sys.modules", {"lettermint": None}):
            with pytest.raises(ImproperlyConfigured, match="lettermint.*not installed"):
                backend.open()

    def test_open_creates_connection(self, settings, mock_lettermint):
        mock_cls, mock_client, _ = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        result = backend.open()
        assert result is True
        assert backend.connection is mock_client
        mock_cls.assert_called_once_with(sending_token="lm_key")

    def test_open_passes_base_url(self, settings, mock_lettermint):
        mock_cls, _, _ = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        settings.LETTERMINT_BASE_URL = "https://custom.api.com"
        backend = LettermintEmailBackend()
        backend.open()
        mock_cls.assert_called_once_with(sending_token="lm_key", base_url="https://custom.api.com")

    def test_open_passes_timeout(self, settings, mock_lettermint):
        mock_cls, _, _ = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        settings.LETTERMINT_TIMEOUT = 45
        backend = LettermintEmailBackend()
        backend.open()
        mock_cls.assert_called_once_with(sending_token="lm_key", timeout=45.0)

    def test_open_twice_returns_false(self, settings, mock_lettermint):
        mock_cls, mock_client, _ = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        backend.open()
        result = backend.open()
        assert result is False
        mock_cls.assert_called_once()


class TestLettermintEmailBackendClose:
    def test_close_calls_sdk_close(self, settings, mock_lettermint):
        _, mock_client, _ = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        backend.open()
        backend.close()
        mock_client.close.assert_called_once()
        assert backend.connection is None

    def test_close_when_not_open_is_safe(self):
        backend = LettermintEmailBackend.__new__(LettermintEmailBackend)
        backend.connection = None
        backend.close()  # should not raise


class TestLettermintEmailBackendSendMessages:
    def test_sends_simple_email(self, settings, mock_lettermint, simple_email):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        count = backend.send_messages([simple_email])
        assert count == 1
        assert sent_payload(mock_emails) == {
            "from": "Sender <sender@example.com>",
            "to": ["recipient@example.com"],
            "subject": "Hello",
            "text": "Plain text body.",
        }

    def test_sends_html_email(self, settings, mock_lettermint, html_email):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        count = backend.send_messages([html_email])
        assert count == 1
        payload = sent_payload(mock_emails)
        assert payload["html"] == "<h1>Hello HTML</h1>"
        assert payload["text"] == "Plain text fallback."

    def test_sends_cc_bcc(self, settings, mock_lettermint):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        msg = EmailMessage(
            subject="Test",
            body="Body",
            from_email="a@example.com",
            to=["b@example.com"],
            cc=["c@example.com"],
            bcc=["d@example.com"],
        )
        backend = LettermintEmailBackend()
        backend.send_messages([msg])
        payload = sent_payload(mock_emails)
        assert payload["cc"] == ["c@example.com"]
        assert payload["bcc"] == ["d@example.com"]

    def test_sends_reply_to(self, settings, mock_lettermint):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        msg = EmailMessage(
            subject="Test",
            body="Body",
            from_email="a@example.com",
            to=["b@example.com"],
            reply_to=["reply@example.com"],
        )
        backend = LettermintEmailBackend()
        backend.send_messages([msg])
        assert sent_payload(mock_emails)["reply_to"] == ["reply@example.com"]

    def test_uses_default_route_from_settings(self, settings, mock_lettermint, simple_email):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        settings.LETTERMINT_ROUTE = "transactional"
        backend = LettermintEmailBackend()
        backend.send_messages([simple_email])
        assert sent_payload(mock_emails)["route"] == "transactional"

    def test_per_message_route_overrides_default(self, settings, mock_lettermint, simple_email):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        settings.LETTERMINT_ROUTE = "default-route"
        simple_email.extra_headers["X-Lettermint-Route"] = "per-message-route"
        backend = LettermintEmailBackend()
        backend.send_messages([simple_email])
        assert sent_payload(mock_emails)["route"] == "per-message-route"

    def test_returns_zero_for_empty_list(self, settings):
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        assert backend.send_messages([]) == 0

    def test_skips_message_with_no_recipients(self, settings, mock_lettermint):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        msg = EmailMessage(subject="No recipients", body="Body", from_email="a@example.com")
        backend = LettermintEmailBackend()
        count = backend.send_messages([msg])
        assert count == 0
        mock_emails.send.assert_not_called()

    def test_returns_count_of_sent(self, settings, mock_lettermint, simple_email, html_email):
        settings.LETTERMINT_API_KEY = "lm_key"
        backend = LettermintEmailBackend()
        count = backend.send_messages([simple_email, html_email])
        assert count == 2

    def test_fail_silently_swallows_exceptions(self, settings, mock_lettermint, simple_email):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        mock_emails.send.side_effect = Exception("API error")
        backend = LettermintEmailBackend(fail_silently=True)
        count = backend.send_messages([simple_email])
        assert count == 0

    def test_raises_exception_when_not_silent(self, settings, mock_lettermint, simple_email):
        _, _, mock_emails = mock_lettermint
        settings.LETTERMINT_API_KEY = "lm_key"
        mock_emails.send.side_effect = Exception("API error")
        backend = LettermintEmailBackend(fail_silently=False)
        with pytest.raises(Exception, match="API error"):
            backend.send_messages([simple_email])


class TestNormalizeAddress:
    def test_full_address(self):
        result = LettermintEmailBackend._normalize_address("Sender <sender@example.com>")
        assert result == "Sender <sender@example.com>"

    def test_bare_email(self):
        result = LettermintEmailBackend._normalize_address("sender@example.com")
        assert result == "sender@example.com"

    def test_invalid_address_raises(self):
        with pytest.raises(ImproperlyConfigured):
            LettermintEmailBackend._normalize_address("not-an-email")


class TestGetHtmlBody:
    def test_returns_html_from_alternatives(self):
        msg = EmailMultiAlternatives(body="text")
        msg.attach_alternative("<p>html</p>", "text/html")
        assert LettermintEmailBackend._get_html_body(msg) == "<p>html</p>"

    def test_returns_empty_when_no_alternatives(self):
        msg = EmailMessage(body="text")
        assert LettermintEmailBackend._get_html_body(msg) == ""
