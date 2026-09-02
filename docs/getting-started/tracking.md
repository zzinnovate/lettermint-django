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
    path("", include("lettermint_django.urls")),
]
```

This exposes `POST /lettermint/message-events/` (URL name `lm-message-events`). The view is CSRF-exempt and only accepts POST.

The path is the setting `LETTERMINT_WEBHOOK_PATH`, so include the URLs at the root and change the setting to move the endpoint:

```python
LETTERMINT_WEBHOOK_PATH = os.getenv("LETTERMINT_WEBHOOK_PATH", "lmnt/events/")   # -> POST /lmnt/events/
```

Register exactly that path in Lettermint, including the trailing slash. `reverse("lm-message-events")` returns it. Including the URLs under a prefix would double the path; the system check `lettermint_django.W001` warns when the resolved URL and the setting disagree.

### 3. Create the webhook in Lettermint

In the Lettermint dashboard open **Webhooks** and add one webhook pointing at `https://your-domain.example/lettermint/message-events/`. One webhook is enough for everything this Django project sends, single or [bulk](bulk.md): events are matched on `message_id`, so the webhook's scope (team, project or route) only needs to cover the routes you send through. For bounce and delivery tracking select at least:

- `message.delivered`
- `message.soft_bounced`
- `message.hard_bounced`
- `message.failed`

Add `message.opened` and `message.clicked` if `not_opened()` should mean anything. Copy the signing secret into `LETTERMINT_WEBHOOK_SECRET`; it holds one secret, so use one webhook per Django project rather than several pointing at the same URL. The dashboard's test button sends a `webhook.test` event, which the endpoint acknowledges without storing anything.

!!! note "What is stored, what is acknowledged"
    Every outbound `message.*` event with a `message_id` is stored as an `LmEmailEvent`, including events this version does not act on (spam complaints, unsubscribes). Only the events listed under [what happens per event](#what-happens-per-event) with a status change the message status. `message.inbound` and the `suppression.*` events are answered with `200` but not stored: inbound mail is not supported, and a `message.inbound` payload carries the complete incoming message. Leave those events unticked for this webhook.

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
| `tag` | Lettermint tag from the `X-Lettermint-Tag` header, e.g. a campaign name |
| `bulk_id` | Id of the [bulk send](bulk.md) this message was part of; empty for single sends |
| `status` | Current status, see [what happens per event](#what-happens-per-event) (starts as `pending`, or `scheduled` for a scheduled send) |
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

### What happens per event

Every delivery is verified and answered with `200`. This is what happens after that, per event as the Lettermint dashboard groups them:

| Event | Stored as `LmEmailEvent` | `LmEmailMessage.status` becomes | Signal |
|---|---|---|---|
| `message.created` | yes | `queued` | `lm_email_event` |
| `message.sent` | yes | `processed` | `lm_email_event` |
| `message.delivered` | yes | `delivered` | + `lm_email_delivered` |
| `message.auto_replied` | yes | unchanged | `lm_email_event` |
| `message.hard_bounced` | yes | `hard_bounced` | + `lm_email_bounced` |
| `message.soft_bounced` | yes | `soft_bounced` | + `lm_email_bounced` |
| `message.failed` | yes | `failed` | + `lm_email_failed` |
| `message.suppressed` | yes | `suppressed` | `lm_email_event` |
| `message.policy_rejected` | yes | `policy_rejected` | `lm_email_event` |
| `message.scheduled` | yes | `scheduled` | `lm_email_event` |
| `message.rescheduled` | yes | `scheduled` | `lm_email_event` |
| `message.released` | yes | `queued` | `lm_email_event` |
| `message.canceled` | yes | `canceled` | `lm_email_event` |
| `message.opened` | yes | `opened` | `lm_email_event` |
| `message.clicked` | yes | `clicked` | `lm_email_event` |
| `message.unsubscribed` | yes | `unsubscribed` | `lm_email_event` |
| `message.spam_complaint` | yes | `spam_complaint` | `lm_email_event` |
| `message.inbound` | no | | none |
| `suppression.added`, `suppression.removed` | no | | none |
| `webhook.test` | no | | none |

The status follows the most recent event by `occurred_at`, so an out-of-order retry of an older event never overwrites a newer status. For a message with several recipients the status reflects the latest event across all of them; use the events for per-recipient detail.

Events Lettermint adds in the future are handled by the same rules, without code changes: an event with a `data.message_id` is stored, with its raw `data`, and leaves the status unchanged until this package maps it; an event without one is acknowledged and ignored. Unknown fields are kept in `data`, unknown value types are stored as text, and values longer than a column are truncated rather than rejected. The only deliveries that get a `5xx` are ones the database could not store, which is exactly when a retry from Lettermint helps.

## Querying

```python
from lettermint_django.models import LmEmailEvent, LmEmailMessage

LmEmailMessage.objects.get_status("msg_...")   # "delivered", "hard_bounced", ... or None
LmEmailMessage.objects.delivered()             # delivered, opened or clicked
LmEmailMessage.objects.bounced()                # soft and hard bounces
LmEmailMessage.objects.failed()
LmEmailMessage.objects.not_delivered()          # bounced, failed, suppressed, or still in transit
LmEmailMessage.objects.not_opened()             # delivered without a registered open or click
LmEmailMessage.objects.tagged("launch-2026")   # everything sent with that tag
LmEmailMessage.objects.from_bulk(bulk_id)       # everything one send_bulk call sent

message = LmEmailMessage.objects.get(message_id="msg_...")
message.bounced                                 # True for soft/hard bounces
message.events.all()                            # newest first

LmEmailEvent.objects.for_recipient("user@example.com")
LmEmailEvent.objects.bounces()
LmEmailEvent.objects.from_bulk(bulk_id)
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

## Security

The endpoint is CSRF-exempt because every delivery is signed. Before anything is read from the body or written to the database, a delivery must pass the checks the Lettermint SDK performs:

1. `X-Lettermint-Signature` and `X-Lettermint-Delivery` headers must be present.
2. The delivery timestamp must be within five minutes of now, which blocks replaying a captured request.
3. The HMAC-SHA256 signature over the timestamp and the raw body must match `LETTERMINT_WEBHOOK_SECRET`, compared in constant time.

Anything else gets a `400` and one warning line in the `lettermint_django` log. A valid delivery that arrives twice within the window is a no-op because of the unique event id. Without `LETTERMINT_WEBHOOK_SECRET` the view raises `ImproperlyConfigured` on every request: it fails closed and never accepts an unsigned delivery.

What stays with you: keep the secret out of the repository, regenerate it in the Lettermint dashboard if it leaks, serve the endpoint over HTTPS (Lettermint requires it), and add rate limiting at your proxy if log noise from bots bothers you.

Two system checks catch the common mistakes at `manage.py check` and `runserver` time: `lettermint_django.W001` when the URLs are included under a prefix, and `lettermint_django.W002` when the webhook is served but the secret is empty.

## Behaviour details

- **Sending never depends on tracking.** If storing the sent message fails, the error is logged and the email still counts as sent.
- **Unknown messages are kept.** Events for messages that were not sent through this app are stored with `email_message=None`.
- **Response codes.** The endpoint returns `400` for an invalid signature, stale timestamp or malformed JSON, and `200` otherwise. A database error results in a `5xx`, after which Lettermint retries the delivery (12 attempts over about 14 hours).
- **Logging.** Rejected deliveries and tracking failures are logged to the `lettermint_django` logger.
