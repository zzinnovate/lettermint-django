# lettermint-django

[![PyPI version](https://img.shields.io/pypi/v/lettermint-django.svg)](https://pypi.org/project/lettermint-django/)
[![Tests](https://github.com/zzinnovate/lettermint-django/actions/workflows/run-tests.yml/badge.svg?branch=main)](https://github.com/zzinnovate/lettermint-django/actions/workflows/run-tests.yml)
[![codecov](https://codecov.io/gh/zzinnovate/lettermint-django/graph/badge.svg)](https://codecov.io/gh/zzinnovate/lettermint-django)
![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)
![Django Version](https://img.shields.io/badge/django-4.2%20%7C%205.x%20%7C%206.x-092E20)

An unofficial Django email backend for [Lettermint](https://lettermint.co/). Drop it in as your `EMAIL_BACKEND` and all Django mail (`send_mail()`, `EmailMessage`, `EmailMultiAlternatives`) routes through the Lettermint API. Supports per-message routing, HTML emails, attachments, and reply-to headers with no changes to your existing email code. An optional tracking application records sent messages and delivery events through Lettermint webhooks.

Built and maintained by [zzinnovate](https://github.com/zzinnovate). Not affiliated with Lettermint.

## Documentation

📖 **[View Full Documentation →](https://zzinnovate.github.io/lettermint-django/)**

- **Getting Started**: [Installation](https://zzinnovate.github.io/lettermint-django/getting-started/installation/) • [Configuration](https://zzinnovate.github.io/lettermint-django/getting-started/configuration/) • [Usage](https://zzinnovate.github.io/lettermint-django/getting-started/usage/) • [Tracking](https://zzinnovate.github.io/lettermint-django/getting-started/tracking/) • [Bulk sending](https://zzinnovate.github.io/lettermint-django/getting-started/bulk/)
- **Reference**: [Settings](https://zzinnovate.github.io/lettermint-django/reference/settings/) • [Backend](https://zzinnovate.github.io/lettermint-django/reference/backend/)
- **Project**: [Contributing](https://zzinnovate.github.io/lettermint-django/project/contributing/) • [Changelog](https://zzinnovate.github.io/lettermint-django/project/changelog/) • [Security](https://zzinnovate.github.io/lettermint-django/project/security/)

## Requirements

- Python 3.11+ (Django 6 requires Python 3.12+)
- Django 4.2, 5.x, or 6.x
- [lettermint](https://github.com/lettermint/lettermint-python) 2.0+

## Install

```bash
pip install lettermint-django

# For development (includes testing tools)
pip install -e ".[dev]"
```

## Quick start

```python
import os

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
```

That's it. All `send_mail()`, `EmailMessage`, and `EmailMultiAlternatives` calls in Django will now route through Lettermint.

## Email tracking (optional)

Add the app, set the webhook secret and include the webhook URL to record every sent message and its delivery events (delivered, bounced, failed):

```python
INSTALLED_APPS += ["lettermint_django"]
LETTERMINT_WEBHOOK_SECRET = os.getenv("LETTERMINT_WEBHOOK_SECRET")

# urls.py
path("", include("lettermint_django.urls")),
```

```bash
python manage.py migrate lettermint_django
```

Point a webhook in the Lettermint dashboard at `/lettermint/message-events/` (change it with `LETTERMINT_WEBHOOK_PATH`). Query `LmEmailMessage` and `LmEmailEvent`, or connect to the `lm_email_bounced` signal. See the [tracking guide](https://zzinnovate.github.io/lettermint-django/getting-started/tracking/).

## Bulk sending

Send the same mail to many people, or a personalised mail to each of them, in batches through Lettermint's batch endpoint:

```python
from lettermint_django.bulk import send_bulk_mail

result = send_bulk_mail(
    [{"email": g.email, "name": g.name, "link": g.invite_url} for g in guests],
    subject="{{ name }}, you are invited",
    text_template="emails/invite.txt",
    html_template="emails/invite.html",
    tag="invites",
)
result.sent_count, result.failed   # per-message outcome, with message ids
```

See the [bulk sending guide](https://zzinnovate.github.io/lettermint-django/getting-started/bulk/).

## Roadmap

This project is actively developed with a clear path toward v1.0.0. Our roadmap includes email tracking, bounce monitoring, and engagement analytics.

- **Current:** v0.3.x (email backend, bounce & delivery tracking via webhooks)
- **Next:** v0.4.0 (bulk sending via the batch endpoint)
- **Planned:** v0.5.0 (opens, clicks, analytics) → v1.0.0 (production-ready)

[View the full roadmap →](https://zzinnovate.github.io/lettermint-django/reference/roadmap/)

## Settings Reference

| Setting | Required | Default | Description |
|---|---|---|---|
| `LETTERMINT_API_KEY` | Yes | - | Your project API token from the Lettermint dashboard |
| `LETTERMINT_BASE_URL` | No | SDK default | Override the Lettermint API base URL |
| `LETTERMINT_ROUTE` | No | - | Default route applied to all outgoing emails |
| `LETTERMINT_TIMEOUT` | No | SDK default | Request timeout in seconds |
| `LETTERMINT_WEBHOOK_SECRET` | With tracking | - | Signing secret of your Lettermint webhook |
| `LETTERMINT_WEBHOOK_PATH` | No | `lettermint/message-events/` | Path of the webhook endpoint |
| `LETTERMINT_BATCH_SIZE` | No | 500 | Messages per request for bulk sending |

## Per-message Route

Override the route for a specific message via `extra_headers`:

```python
from django.core.mail import EmailMessage

msg = EmailMessage(
    subject="Password reset",
    body="Click the link...",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
msg.extra_headers["X-Lettermint-Route"] = "transactional"
msg.send()
```

## HTML Emails

```python
from django.core.mail import EmailMultiAlternatives

msg = EmailMultiAlternatives(
    subject="Welcome",
    body="Plain text fallback.",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
msg.attach_alternative("<h1>Hello!</h1>", "text/html")
msg.send()
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and workflow guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities and best practices.

## Credits

This package is built on top of the official [lettermint Python SDK](https://github.com/lettermint/lettermint-python), which handles all API communication. 

- [Sjoerd Zaalberg van Zelst](https://github.com/sjoerdzzid) (zzinnovate)
- [All contributors](https://github.com/zzinnovate/lettermint-django/graphs/contributors)

## License

MIT. See [LICENSE](LICENSE).