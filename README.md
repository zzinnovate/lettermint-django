# lettermint-django

Django email backend for [Lettermint](https://lettermint.co/) - send Django emails via the Lettermint API.

## Installation

```bash
pip install lettermint-django
```

## Configuration

Add to your Django settings:

```python
EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = "lm_your_api_key"
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

## Requirements

- Python 3.11+
- Django 4.2+
- [lettermint](https://github.com/lettermint/lettermint-python) 2.0+

## License

MIT. See [LICENSE](LICENSE).