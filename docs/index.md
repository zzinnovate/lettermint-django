# lettermint-django

An unofficial Django email backend for the [Lettermint](https://lettermint.co/) API. Open source, not affiliated with Lettermint. Maintained by [zzinnovate](https://github.com/zzinnovate). 

[![PyPI version](https://img.shields.io/pypi/v/lettermint-django.svg)](https://pypi.org/project/lettermint-django/)
[![Tests](https://github.com/zzinnovate/lettermint-django/actions/workflows/run-tests.yml/badge.svg?branch=main)](https://github.com/zzinnovate/lettermint-django/actions/workflows/run-tests.yml)
[![codecov](https://codecov.io/gh/zzinnovate/lettermint-django/graph/badge.svg)](https://codecov.io/gh/zzinnovate/lettermint-django)
![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)
![Django Version](https://img.shields.io/badge/django-4.2%20%7C%205.x%20%7C%206.x-092E20)



## Quick start

Available on [PyPI](https://pypi.org/project/lettermint-django/). Install and configure:

```bash
pip install lettermint-django
```

```python
import os

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
```

That's it. All Django `send_mail()`, `EmailMessage`, and `EmailMultiAlternatives` calls now route through Lettermint.

## Tracking and bulk sending (optional)

Add the app, include the webhook URLs at the root of your URLconf and set the webhook secret:

```python
INSTALLED_APPS += ["lettermint_django"]
LETTERMINT_WEBHOOK_SECRET = os.getenv("LETTERMINT_WEBHOOK_SECRET")

# urls.py
path("", include("lettermint_django.urls")),   # POST /lettermint/message-events/
```

```bash
python manage.py migrate lettermint_django
```

Every sent message is then stored with its Lettermint `message_id`, and the webhook keeps its delivery status current: delivered, bounced, failed. See [Tracking](getting-started/tracking.md). For many recipients, `lettermint_django.bulk.send_bulk_mail()` sends one personalised message per recipient through the batch endpoint; see [Bulk sending](getting-started/bulk.md).

## Features

- **No SMTP required**:  sends via the Lettermint HTTP API
- **Django-native**:  works with all standard Django mail helpers
- **Per-message routing and tags**:  override the route or set a tag per email via `extra_headers`
- **HTML support**:  `EmailMultiAlternatives` with `text/html` alternative works out of the box
- **Delivery tracking**:  optional app that records sent messages and their webhook events (delivered, bounced, failed), with Django signals
- **Bulk sending**:  one mail to many or a unique mail per recipient, in batches, with per-message results
- **Minimal dependencies**:  only `lettermint` (official SDK) on top of Django

## Common operations

```python
from django.core.mail import send_mail, EmailMessage, EmailMultiAlternatives
import os

# Simple email
send_mail(
    subject="Hello",
    message="Plain text body.",
    from_email="noreply@example.com",
    recipient_list=["user@example.com"],
)

# HTML email
msg = EmailMultiAlternatives(
    subject="Welcome",
    body="Plain text fallback.",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
msg.attach_alternative("<h1>Hello!</h1>", "text/html")
msg.send()

# Per-message route override
msg = EmailMessage(
    subject="Password reset",
    body="Click the link...",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
msg.extra_headers["X-Lettermint-Route"] = "app-priority"
msg.send()
```
