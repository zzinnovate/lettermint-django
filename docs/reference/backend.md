# Backend

`LettermintEmailBackend` is a Django email backend that sends mail via the Lettermint HTTP API. It subclasses `BaseEmailBackend` and integrates with Django's standard `send_mail` and `EmailMessage` interfaces. It supports attachments, CC/BCC, reply-to, custom headers, and per-message route overrides out of the box.

## Class

```
lettermint_django.LettermintEmailBackend 
```

Subclasses `django.core.mail.backends.base.BaseEmailBackend`.

## Methods

### `open()`

Initialises the Lettermint SDK client using `LETTERMINT_API_KEY` (and optionally `LETTERMINT_BASE_URL` and `LETTERMINT_TIMEOUT`). Called automatically when sending messages.

### `close()`

Releases the SDK client. Called automatically after sending.

### `send_messages(email_messages)`

Sends a list of `EmailMessage` objects. Returns the number of messages successfully sent.

Each message is translated to the Lettermint SDK chain: `from_()`, `to()`, `cc()`, `bcc()`, `subject()`, `text()`, `html()`, `reply_to()`, `headers()`, `attach()`, `route()`, `send()`.

## Per-message route override

Set `X-Lettermint-Route` in `extra_headers` to override the global `LETTERMINT_ROUTE` for a single message:

```python
msg.extra_headers["X-Lettermint-Route"] = "transactional"
```

## Error handling

If sending fails, the error is handled according to Django's `fail_silently` setting on the backend. When `fail_silently=False` (the default), exceptions propagate. When `fail_silently=True`, errors are suppressed and the message is skipped.

```python
from django.core.mail import get_connection

# Suppress errors per-connection
connection = get_connection(fail_silently=True)
```
