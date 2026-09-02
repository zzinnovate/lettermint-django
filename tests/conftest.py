"""Test fixtures for lettermint-django."""

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives

WEBHOOK_SECRET = "whsec_test_secret"


@pytest.fixture(autouse=True)
def _enable_db_access(db):
    """Every test may touch the database (tracking writes rows on send)."""


@pytest.fixture
def api_key():
    return "lm_test_api_key_12345"


@pytest.fixture
def simple_email():
    return EmailMessage(
        subject="Hello",
        body="Plain text body.",
        from_email="Sender <sender@example.com>",
        to=["recipient@example.com"],
    )


@pytest.fixture
def html_email():
    msg = EmailMultiAlternatives(
        subject="Hello HTML",
        body="Plain text fallback.",
        from_email="Sender <sender@example.com>",
        to=["recipient@example.com"],
    )
    msg.attach_alternative("<h1>Hello HTML</h1>", "text/html")
    return msg


@pytest.fixture
def mock_lettermint():
    """Patch the Lettermint SDK client with a fluent builder mock."""
    with patch("lettermint.Lettermint") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_email_builder = MagicMock()
        mock_client.email = mock_email_builder
        for method in (
            "from_", "to", "cc", "bcc", "reply_to", "route",
            "subject", "text", "html", "headers", "attach",
        ):
            getattr(mock_email_builder, method).return_value = mock_email_builder
        mock_email_builder.send.return_value = {"message_id": "msg_test_1", "status": "pending"}
        yield mock_cls, mock_client, mock_email_builder


def sign_webhook(body, secret=WEBHOOK_SECRET, timestamp=None):
    """Return request headers signed the way Lettermint signs deliveries."""
    timestamp = int(time.time()) if timestamp is None else int(timestamp)
    digest = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return {
        "X-Lettermint-Signature": f"t={timestamp},v1={digest}",
        "X-Lettermint-Delivery": str(timestamp),
        "X-Lettermint-Event": json.loads(body).get("event", "") if body.startswith("{") else "",
        "X-Lettermint-Attempt": "1",
    }


def webhook_payload(event, message_id="msg_test_1", event_id="evt_1", recipient="recipient@example.com",
                    timestamp="2026-09-01T10:00:00Z", **data):
    """Build a Lettermint webhook envelope for a message event."""
    body_data = {
        "message_id": message_id,
        "subject": "Hello",
        "recipient": recipient,
        "metadata": {},
        "tag": None,
        "tags": [],
    }
    body_data.update(data)
    return {
        "id": event_id,
        "event": event,
        "timestamp": timestamp,
        "context": {"scope": "project", "team_id": "team_1", "project_id": "proj_1", "route_id": None},
        "data": body_data,
    }


@pytest.fixture
def post_webhook(client):
    """POST a payload dict (or raw string) to the webhook endpoint, signed unless told otherwise."""

    def _post(payload, *, secret=WEBHOOK_SECRET, timestamp=None, headers=None, sign=True):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        request_headers = sign_webhook(body, secret=secret, timestamp=timestamp) if sign else {}
        request_headers.update(headers or {})
        return client.post(
            "/lettermint/message-events/",
            data=body,
            content_type="application/json",
            headers=request_headers,
        )

    return _post
