# Usage

Once configured, use Django's standard mail helpers as usual, no API-specific imports needed.

## Simple email

```python
from django.core.mail import send_mail

send_mail(
    subject="Hello from Django",
    message="Plain text body.",
    from_email="noreply@example.com",
    recipient_list=["user@example.com"],
)
```

## HTML email

```python
from django.core.mail import EmailMultiAlternatives

msg = EmailMultiAlternatives(
    subject="Welcome",
    body="Plain text fallback.",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
msg.attach_alternative("<h1>Welcome aboard!</h1>", "text/html")
msg.send()
```

## CC, BCC, Reply-To

```python
from django.core.mail import EmailMessage

msg = EmailMessage(
    subject="Project update",
    body="Here is the latest update.",
    from_email="team@example.com",
    to=["client@example.com"],
    cc=["manager@example.com"],
    bcc=["archive@example.com"],
    reply_to=["support@example.com"],
)
msg.send()
```

## Attachments

```python
from django.core.mail import EmailMessage

msg = EmailMessage(
    subject="Invoice",
    body="Please find the attached invoice.",
    from_email="billing@example.com",
    to=["client@example.com"],
)
msg.attach("invoice.pdf", pdf_bytes, "application/pdf")
msg.send()
```

## Per-message route override

Override the Lettermint route for a specific message using `extra_headers`:

```python
from django.core.mail import EmailMessage

msg = EmailMessage(
    subject="Password reset",
    body="Click the link to reset your password.",
    from_email="noreply@example.com",
    to=["user@example.com"],
)
msg.extra_headers["X-Lettermint-Route"] = "transactional"
msg.send()
```

The `X-Lettermint-Route` header takes precedence over the global `LETTERMINT_ROUTE` setting.

## Sending multiple messages

Django's connection can be reused across multiple sends:

```python
from django.core.mail import get_connection, EmailMessage

connection = get_connection()
messages = [
    EmailMessage("Subject 1", "Body 1", "from@example.com", ["a@example.com"]),
    EmailMessage("Subject 2", "Body 2", "from@example.com", ["b@example.com"]),
]
connection.send_messages(messages)
```
