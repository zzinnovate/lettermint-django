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

Each message is translated with `build_payload()` and sent through the SDK's single-send builder.

### `send_single(email_message)`

Sends one message and returns the Lettermint response dict (`message_id`, `status`), or `None` when the message has no recipients. SDK errors propagate. `_send()` is kept as an alias.

### `build_payload(email_message)`

Translates a Django `EmailMessage` into the dict the Lettermint API accepts: `from`, `to`, `cc`, `bcc`, `reply_to`, `route`, `subject`, `text`, `html`, `headers`, `tag` and base64 `attachments`. The single-send and batch paths both use it, so a subclass that overrides `_get_passthrough_headers()` affects both.

### `send_payloads(payloads)`

Posts a list of payload dicts to the batch endpoint in one request and returns Lettermint's per-message responses, in the order it was asked. `send_bulk()` does not lean on that order alone; see [bulk sending](../getting-started/bulk.md#batches-failures-and-limits). It does not chunk or check Lettermint's limits; whatever Lettermint rejects comes back as the SDK's exception. This is the primitive behind [bulk sending](../getting-started/bulk.md); use `lettermint_django.bulk.send_bulk()` rather than calling it directly.

## Per-message route and tag

Set `X-Lettermint-Route` in `extra_headers` to override the global `LETTERMINT_ROUTE` for a single message, and `X-Lettermint-Tag` to tag it:

```python
msg.extra_headers["X-Lettermint-Route"] = "transactional"
msg.extra_headers["X-Lettermint-Tag"] = "launch-2026"
```

Both headers are consumed by the backend and not sent as email headers.

## Error handling

If sending fails, the error is handled according to Django's `fail_silently` setting on the backend. When `fail_silently=False` (the default), exceptions propagate. When `fail_silently=True`, errors are suppressed and the message is skipped.

```python
from django.core.mail import get_connection

# Suppress errors per-connection
connection = get_connection(fail_silently=True)
```
