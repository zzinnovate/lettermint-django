# lettermint-django

[![PyPI version](https://img.shields.io/pypi/v/lettermint-django.svg)](https://pypi.org/project/lettermint-django/)
[![Tests](https://github.com/zzinnovate/lettermint-django/actions/workflows/run-tests.yml/badge.svg?branch=main)](https://github.com/zzinnovate/lettermint-django/actions/workflows/run-tests.yml)
[![codecov](https://codecov.io/gh/zzinnovate/lettermint-django/graph/badge.svg)](https://codecov.io/gh/zzinnovate/lettermint-django)
![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)

An unofficial Django email backend for [Lettermint](https://lettermint.co/) — send Django emails via the Lettermint API instead of SMTP.

Built and maintained by [zzinnovate](https://github.com/zzinnovate). Not affiliated with Lettermint.

## Documentation

📖 **[View Full Documentation →](https://zzinnovate.github.io/lettermint-django/)**

- **Getting Started** — [Installation](https://zzinnovate.github.io/lettermint-django/getting-started/installation/) • [Configuration](https://zzinnovate.github.io/lettermint-django/getting-started/configuration/) • [Usage](https://zzinnovate.github.io/lettermint-django/getting-started/usage/)
- **Reference** — [Settings](https://zzinnovate.github.io/lettermint-django/reference/settings/) • [Backend](https://zzinnovate.github.io/lettermint-django/reference/backend/)
- **Project** — [Contributing](https://zzinnovate.github.io/lettermint-django/project/contributing/) • [Changelog](https://zzinnovate.github.io/lettermint-django/project/changelog/) • [Security](https://zzinnovate.github.io/lettermint-django/project/security/)

## Requirements

- Python 3.11+
- Django 4.2+
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

## Settings Reference

| Setting | Required | Default | Description |
|---|---|---|---|
| `LETTERMINT_API_KEY` | Yes | - | Your project API token from the Lettermint dashboard |
| `LETTERMINT_BASE_URL` | No | SDK default | Override the Lettermint API base URL |
| `LETTERMINT_ROUTE` | No | - | Default route applied to all outgoing emails |
| `LETTERMINT_TIMEOUT` | No | SDK default | Request timeout in seconds |

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

- [Sjoerd Zaalberg van Zelst](https://github.com/sjoerdzzid) (zzinnovate)
- [All contributors](https://github.com/zzinnovate/lettermint-django/graphs/contributors)

## License

MIT. See [LICENSE](LICENSE).