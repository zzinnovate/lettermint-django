"""Test fixtures for lettermint-django."""

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives


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
