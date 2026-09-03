# Bulk Sending

Send one mail to many people, or a unique mail to each person, through Lettermint's batch endpoint. Messages go out in batches (500 per request by default), every message gets its own `message_id`, and with [tracking](tracking.md) installed every message gets its own `LmEmailMessage` row.

Import from `lettermint_django.bulk`. Two entry points:

- `send_bulk_mail()` renders one message per recipient from templates and sends them. Use this for the common case.
- `send_bulk()` sends any iterable of Django `EmailMessage` objects or prepared payload dicts. Use this when you build the messages yourself, or somewhere else.

Both return a `BulkResult` with a per-message outcome. Nothing is queued and nothing is retried: the call sends what you give it, synchronously, and tells you per message whether Lettermint accepted it and, if not, why. Run large sends from a background task, not from a request.

## Same mail to everyone

```python
from lettermint_django.bulk import send_bulk_mail

result = send_bulk_mail(
    ["ann@example.com", "bob@example.com", "cy@example.com"],
    subject="Doors open at 19:00",
    text_template="emails/announcement.txt",
    html_template="emails/announcement.html",
    context={"event": event},
    tag="doors-2026",
)
```

Each address still becomes its own message. Recipients never see each other.

## A unique mail per person

Pass mappings instead of addresses. Every key is available in the templates; `email` is required, `name` is used for the display name and `language` switches the active translation for that recipient.

```python
recipients = [
    {"email": guest.email, "name": guest.first_name, "link": guest.invite_url, "language": "nl"}
    for guest in guests
]

result = send_bulk_mail(
    recipients,
    subject="{{ name }}, you are invited to {{ event.title }}",
    text_template="emails/invite.txt",
    html_template="emails/invite.html",
    context={"event": event},
    from_email="Events <events@example.com>",
    tag=f"invite-{event.pk}",
)
```

A recipient's own keys win over `context` when they clash. The templates also get `email`, `name` and `recipient` (the mapping you passed in).

## Routes

A list send produces bounces and complaints that a transactional stream does not, so give bulk its own Lettermint route and keep the two reputations apart. One setting covers every bulk send in the project:

```python
LETTERMINT_ROUTE = "app-mail"        # slug of the route for everything else
LETTERMINT_BULK_ROUTE = "app-lists"  # slug of the route for send_bulk() and send_bulk_mail()
```

Both take a route **slug**. A Lettermint route has a type of its own, `transactional`, `broadcast` or `inbound`, which this package never sees: it passes on the slug you configured. Which type each of your routes has, and which one is the default of your API key, is yours to check in the dashboard.

Set both. A route you do not name is the default route of your API key, and that default is invisible from here: leave either setting empty and that stream rides on whatever the dashboard happens to say today. A bulk send with no route at all logs a warning naming this setting.

Override per send with `route=`, and per message with the `X-Lettermint-Route` header. Highest wins:

| Where | Wins over |
|---|---|
| The message's own `X-Lettermint-Route` header, which is what `route=` on `send_bulk_mail()` sets | everything below |
| `route=` on `send_bulk()` | the settings |
| `LETTERMINT_BULK_ROUTE` | `LETTERMINT_ROUTE` |
| `LETTERMINT_ROUTE`, or the `route` of the connection | the default route of your API key |

`tag=` on `send_bulk()` works the same way: it tags the whole send unless a message carries its own `X-Lettermint-Tag`.

A prepared payload dict is left as it was composed: a `route` or `tag` already in it stands, and the send-wide value only fills in what the payload left open.

## Templates

| Argument | What it is |
|---|---|
| `subject` | A template **string**. Rendered per recipient and collapsed to one line. |
| `text`, `html` | Template **strings** for the plain-text and HTML body. |
| `text_template`, `html_template` | Template **names**, loaded through Django's template engines like `render_to_string`. |
| `context` | Shared context for every recipient. |
| `request` | Passed to template rendering, so context processors work. |
| `language` | Default language code; a recipient's own `language` key overrides it. |

`subject` and `text` strings render with autoescaping off, so `A & B` stays `A & B`. Template files keep whatever they declare, exactly as with `render_to_string`; wrap plain-text files in `{% autoescape off %}` as usual. At least one of `text`, `html`, `text_template` or `html_template` is required.

Other arguments map straight onto `EmailMessage`: `from_email`, `reply_to`, `headers`, plus `route` and `tag`, which become the `X-Lettermint-Route` and `X-Lettermint-Tag` headers.

## Results

```python
result = send_bulk_mail(...)

result.sent_count      # messages Lettermint accepted
result.failed_count    # messages that did not go out
result.message_ids     # Lettermint ids of the accepted messages
result.bulk_id         # id of this send; stored on every LmEmailMessage it created
bool(result)           # True only when everything was accepted

for item in result.failed:
    print(item.recipient, item.reason)

for item in result.sent:
    guest = item.recipient          # the mapping you passed in
    guest.last_message_id = item.message_id
```

Each `BulkItem` has:

| Attribute | Meaning |
|---|---|
| `ok` | Lettermint accepted the message |
| `message_id`, `status` | From Lettermint's response, when accepted |
| `error` | The exception that stopped the message, else `None` |
| `reason` | That error as text, with Lettermint's HTTP status and response body when there is one |
| `recipient` | The entry you passed to `send_bulk_mail`, else the first `to` address |
| `to` | The addresses the message was for, without `cc` and `bcc` |
| `recipients` | All addresses in `to`, `cc` and `bcc` |
| `payload` | The dict that was sent to Lettermint |
| `email_message` | The Django message it was built from, or `None` for a payload dict |

A bulk send never raises for individual messages. Configuration errors, such as a missing API key, do raise.

Store `item.message_id` on your own records to join webhook events back to them later through `LmEmailMessage.objects.get_status()` or `LmEmailEvent.objects.filter(message_id=...)`. Store `result.bulk_id` on the thing you sent for (the event, the guest list) to find the whole send again; see [Following up on a send](#following-up-on-a-send).

`bulk_id` is generated per call. Pass your own with `bulk_id=` to make several calls count as one send, for example one call per serverless invocation.

## Building messages yourself

When rendering needs more than templates and variables, build the `EmailMessage` objects and hand them to `send_bulk`. A generator keeps memory flat: messages are pulled one at a time, a batch's worth before each request, so rendering is interleaved with sending. Pass a list instead when you want all rendering done before the first request goes out.

```python
from django.core.mail import EmailMultiAlternatives
from django.utils import translation

from lettermint_django.bulk import send_bulk


def invitations(tokens):
    for token in tokens:
        allowed, reason, _ = token.can_email()
        if not allowed:
            continue
        with translation.override(token.invitation.locale.language_code):
            message = EmailMultiAlternatives(
                subject=..., body=..., from_email=..., to=[token.invitation.email],
                headers={"X-Lettermint-Tag": "invites"},
            )
            message.attach_alternative(..., "text/html")
        message.token = token            # any attribute survives into the result
        yield message


result = send_bulk(invitations(tokens))
for item in result.sent:
    item.email_message.token.register_email_sent(item.message_id)
```

The per-message `X-Lettermint-Tag` header above is one way; `send_bulk(messages, tag="invites", route="broadcast")` tags and routes the whole send in one place instead.

`send_bulk` uses `connection.build_payload()` for every message, so a backend subclass that adds headers in `_get_passthrough_headers()` applies to bulk sends too.

## Preparing elsewhere: queues and serverless

Rendering and sending do not have to happen in the same place, or on the same machine. `LettermintEmailBackend.build_payload()` turns a message into the plain dict Lettermint receives, and `send_bulk` accepts those dicts directly. The dicts are JSON, so they can sit in a queue, a blob or a cache in between.

```python
import json

from lettermint_django import LettermintEmailBackend
from lettermint_django.bulk import render_bulk_mail, send_bulk

# Where the data lives: render once, store as JSON. No API key needed here.
backend = LettermintEmailBackend()
payloads = [backend.build_payload(message) for message in render_bulk_mail(recipients, subject, ...)]
queue.put(json.dumps(payloads))

# Where the sending happens: a worker, a scheduled job, or a function per batch.
result = send_bulk(json.loads(queue.get()))
```

Points to keep in mind:

- A function that receives at most one batch's worth of payloads (500 by default) makes exactly one request per invocation. Split larger jobs before you enqueue them.
- Attachments are base64 inside the dict, so the JSON is as large as the mail.
- Tracking rows are created on the sending side, where the `message_id` comes back. `item.recipient` is the first `to` address for a dict; keep your own key in the queue message if you need more.
- `send_bulk` is synchronous and consumes a synchronous iterable. An `async` generator cannot be passed; render in your async code first and hand the resulting list or dicts to `send_bulk`.

## Following up on a send

With [tracking](tracking.md) installed, every accepted message has an `LmEmailMessage` row that carries the `bulk_id` of the send, and the webhook keeps its `status` current. That is what you need to see how a send went and to act on it: the messages, the webhook data, and the knowledge that they belong together. Bodies are not stored, so a resend comes from your own data, which is why you keep `item.message_id` on your own rows.

```python
from lettermint_django.models import LmEmailMessage

sent = LmEmailMessage.objects.from_bulk(guestlist.bulk_id)

sent.bounced()            # soft and hard bounces, reason on message.events
sent.not_delivered()      # bounced, failed, suppressed, or no delivery confirmation yet
sent.not_opened()         # delivered, but no open or click registered
sent.delivered()
```

Resend to the people behind those rows, single or in bulk, by joining on the `message_id` you stored:

```python
bounced_ids = sent.bounced().values("message_id")
guests = Guest.objects.filter(last_message_id__in=bounced_ids)

result = send_bulk_mail(
    [{"email": g.email, "name": g.name, "link": g.invite_url} for g in guests],
    subject=..., text_template=..., html_template=...,
    bulk_id=guestlist.bulk_id,          # keep counting it as the same send, or leave it out for a new one
)
for item in result.sent:
    item.recipient["guest"].last_message_id = item.message_id   # a resend gets a new message_id
```

A single resend is the same call with one recipient, or a plain `send_mail`; that message then has an empty `bulk_id`.

Two things to know when reading these statuses:

- "Not delivered" includes messages that are simply still in transit. Combine with `created_at` before treating them as lost.
- "Not opened" means no open was registered. Open tracking depends on the recipient loading images and is defeated by mail privacy features, so treat it as a hint, never as proof. It also needs the `message.opened` event on your webhook and open tracking enabled for the message.

## Batches, failures and limits

- Messages go out in chunks of `LETTERMINT_BATCH_SIZE` (default 500), one request per chunk. Override per call with `batch_size=`.
- A chunk that Lettermint rejects fails every message in it, each with `error` and `reason`. The next chunk is still sent, so a single bad batch never blocks the rest.
- Nothing is retried. If you want to isolate the bad message in a rejected chunk, resend those messages one per request yourself:

    ```python
    result = send_bulk(messages)
    retry = send_bulk([item.email_message for item in result.failed], batch_size=1)
    ```

- A timeout is not a confirmed failure: Lettermint may have accepted the batch before the connection dropped. Check `LmEmailMessage` or your webhook events before resending.
- Answers are matched to messages on the recipient address where Lettermint names one, and on request order where it does not. An answer that cannot be placed leaves its message in `result.failed` with a reason naming the mismatch. Those messages may still have gone out: check `LmEmailMessage` or your webhook events before resending, as with a timeout.
- A message without recipients, or one whose payload cannot be built (an invalid sender address, say), is reported as failed and never sent.

Assume that Lettermint accepts a limited number of messages per batch request and a limited request size, and that your plan comes with a monthly quota and spend limit beyond which requests are rejected. Those limits are Lettermint's and can change; this package does not enforce them. Check [Lettermint's documentation](https://lettermint.co/docs) for the current numbers and adjust `LETTERMINT_BATCH_SIZE` if needed. Whatever Lettermint rejects comes back per message in `reason`.
