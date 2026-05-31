# lettermint-django

An unofficial Django email backend for the [Lettermint](https://lettermint.co/) API. Drop SMTP:  send Django emails directly via the Lettermint API with one setting change.

Maintained by [zzinnovate](https://github.com/zzinnovate). Open source, community-friendly, and actively maintained. Not affiliated with Lettermint.

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

## Features

- **No SMTP required**:  sends via the Lettermint HTTP API
- **Django-native**:  works with all standard Django mail helpers
- **Per-message routing**:  override the route per email via `extra_headers`
- **HTML support**:  `EmailMultiAlternatives` with `text/html` alternative works out of the box
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
msg.extra_headers["X-Lettermint-Route"] = "transactional"
msg.send()
```
