# Email Tracking

Track delivery status and bounces for every email you send through Lettermint. Tracking is optional and is switched on by adding `lettermint_django` to `INSTALLED_APPS`. Without it, the backend only sends.

## How it works

1. When the backend sends an email, the `message_id` returned by the Lettermint API is stored as an `LmEmailMessage`.
2. Lettermint calls your webhook endpoint on every status change (delivered, bounced, failed, ...).
3. The endpoint verifies the signature, stores an `LmEmailEvent`, updates the message status and emits a Django signal.

Webhooks are processed synchronously and idempotently. A delivery that Lettermint retries with the same event id is acknowledged but not stored twice.

## Setup

### 1. Install the app and run migrations

```python
import os

INSTALLED_APPS = [
    # ...
    "lettermint_django",
]

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
LETTERMINT_WEBHOOK_SECRET = os.getenv("LETTERMINT_WEBHOOK_SECRET")
```

```bash
python manage.py migrate lettermint_django
```

### 2. Add the webhook URL

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("lettermint/", include("lettermint_django.urls")),
]
```

This exposes `POST /lettermint/message-events/` (URL name `lm-message-events`). The view is CSRF-exempt and only accepts POST. Any prefix works; `lettermint/` is just the example used here.

### 3. Create the webhook in Lettermint

In the Lettermint dashboard open **Webhooks**, add a webhook pointing at `https://your-domain.example/lettermint/message-events/` and select the events you want. For bounce and delivery tracking select at least:

- `message.delivered`
- `message.soft_bounced`
- `message.hard_bounced`
- `message.failed`

Copy the signing secret into `LETTERMINT_WEBHOOK_SECRET`. The dashboard's test button sends a `webhook.test` event, which the endpoint acknowledges without storing anything.

!!! note "All message events are stored"
    Every `message.*` event Lettermint sends is stored as an `LmEmailEvent`, including events this version does not act on (opens, clicks, spam complaints). Only the events in the [status mapping](#status-mapping) change the message status.

## Models

Import from `lettermint_django.models`.

### `LmEmailMessage`

One row per email sent through the backend.

| Field | Description |
|---|---|
| `message_id` | Lettermint message id (unique) |
| `from_email`, `to`, `cc`, `bcc` | Sender and recipient lists as passed to Django |
| `subject` | Subject line |
| `route` | Lettermint route used, if any |
| `status` | Current status, see mapping below (starts as `pending`) |
| `status_changed_at` | Timestamp of the event that set the current status |
| `created_at` | When the message was sent |

Message bodies and attachments are not stored.

### `LmEmailEvent`

One row per webhook event. A message with several recipients gets one event per recipient.

| Field | Description |
|---|---|
| `event_id` | Lettermint event id (unique, used for de-duplication) |
| `email_message` | Related `LmEmailMessage`, or `None` for messages not sent through this app |
| `message_id` | Lettermint message id |
| `event` | Event type, e.g. `message.hard_bounced` |
| `recipient` | Recipient address this event is about |
| `reason` | Human-readable reason: the SMTP response for bounces, `reason` for failures |
| `reason_code` | Enhanced SMTP status code for bounces (e.g. `5.1.1`), `reason_code` for failures |
| `data` | Raw `data` object of the webhook payload |
| `occurred_at` | Event timestamp from Lettermint |

### Status mapping

| Webhook event | `LmEmailMessage.status` |
|---|---|
| `message.created` | `queued` |
| `message.sent` | `processed` |
| `message.delivered` | `delivered` |
| `message.soft_bounced` | `soft_bounced` |
| `message.hard_bounced` | `hard_bounced` |
| `message.failed` | `failed` |
| `message.spam_complaint` | `spam_complaint` |
| `message.suppressed` | `suppressed` |
| `message.policy_rejected` | `policy_rejected` |
| `message.unsubscribed` | `unsubscribed` |
| `message.opened` | `opened` |
| `message.clicked` | `clicked` |

The status follows the most recent event by `occurred_at`, so an out-of-order retry of an older event never overwrites a newer status. For a message with several recipients the status reflects the latest event across all of them; use the events for per-recipient detail.

## Querying

```python
from lettermint_django.models import LmEmailEvent, LmEmailMessage

LmEmailMessage.objects.get_status("msg_...")   # "delivered", "hard_bounced", ... or None
LmEmailMessage.objects.delivered()
LmEmailMessage.objects.bounced()                # soft and hard bounces
LmEmailMessage.objects.failed()

message = LmEmailMessage.objects.get(message_id="msg_...")
message.bounced                                 # True for soft/hard bounces
message.events.all()                            # newest first

LmEmailEvent.objects.for_recipient("user@example.com")
LmEmailEvent.objects.bounces()
```

## Signals

Import from `lettermint_django.signals`. All signals pass `sender=LmEmailEvent` and the keyword arguments `event` (the stored `LmEmailEvent`) and `email_message` (the matching `LmEmailMessage`, or `None`).

| Signal | Sent for |
|---|---|
| `lm_email_event` | Every stored `message.*` event |
| `lm_email_delivered` | `message.delivered` |
| `lm_email_bounced` | `message.soft_bounced`, `message.hard_bounced` |
| `lm_email_failed` | `message.failed` |

```python
from django.dispatch import receiver

from lettermint_django.signals import lm_email_bounced


@receiver(lm_email_bounced)
def handle_bounce(sender, event, email_message, **kwargs):
    if event.event == "message.hard_bounced":
        mark_address_invalid(event.recipient, reason=event.reason_code)
```

Receivers run synchronously inside the webhook request. Exceptions raised by a receiver are logged and swallowed, so a broken receiver never causes Lettermint to retry the delivery. Keep receivers fast; offload slow work to a task queue.

## Admin

When `django.contrib.admin` is installed, both models appear under **Lettermint** as read-only lists. Messages show their events inline.

## Behaviour details

- **Sending never depends on tracking.** If storing the sent message fails, the error is logged and the email still counts as sent.
- **Unknown messages are kept.** Events for messages that were not sent through this app are stored with `email_message=None`.
- **Response codes.** The endpoint returns `400` for an invalid signature, stale timestamp or malformed JSON, and `200` otherwise. A database error results in a `5xx`, after which Lettermint retries the delivery (12 attempts over about 14 hours).
- **Logging.** Rejected deliveries and tracking failures are logged to the `lettermint_django` logger.
