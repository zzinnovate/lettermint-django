# Settings Reference

All settings are read from your Django settings module.

## Required

| Setting | Type | Description |
|---|---|---|
| `LETTERMINT_API_KEY` | `str` | Your project sending token from the Lettermint dashboard (not a team token) |

## Optional

| Setting | Type | Default | Description |
|---|---|---|---|
| `LETTERMINT_BASE_URL` | `str` | SDK default | Override the Lettermint API base URL |
| `LETTERMINT_ROUTE` | `str` | `None` | Default route applied to all outgoing emails |
| `LETTERMINT_BULK_ROUTE` | `str` | `None` | Route applied to [bulk sends](../getting-started/bulk.md), overriding `LETTERMINT_ROUTE` for those messages |
| `LETTERMINT_TIMEOUT` | `int` | SDK default | Request timeout in seconds |
| `LETTERMINT_BATCH_SIZE` | `int` | `500` | Messages per request for [bulk sending](../getting-started/bulk.md). Assumes Lettermint's batch limit; check their documentation |
| `LETTERMINT_WEBHOOK_PATH` | `str` | `lettermint/message-events/` | Full path of the webhook endpoint, with `lettermint_django.urls` included at the root |
| `LETTERMINT_WEBHOOK_SECRET` | `str` | `None` | Signing secret of your Lettermint webhook. Required by the webhook endpoint when [tracking](../getting-started/tracking.md) is installed |

## Tracking and privacy

Only read when `lettermint_django` is in `INSTALLED_APPS`. Every default keeps what earlier versions stored; see [privacy](../getting-started/tracking.md#privacy).

| Setting | Type | Default | Description |
|---|---|---|---|
| `LETTERMINT_TRACKING` | `bool` | `True` | `False` stores nothing new. Models, admin and webhook URL stay; the webhook still answers `200` |
| `LETTERMINT_TRACK_UNKNOWN_MESSAGES` | `bool` | `True` | `False` ignores webhook events for messages this app did not record, including those sent with `X-Lettermint-Track: false` |
| `LETTERMINT_TRACKING_SUBJECT` | `bool` | `True` | `False` stores an empty `LmEmailMessage.subject` and leaves `subject` out of event `data` |
| `LETTERMINT_TRACKING_EVENT_DATA` | `str` | `"full"` | What `LmEmailEvent.data` keeps: `"full"`, `"minimal"` (message id, tags, reason fields and the enhanced status code) or `"none"` |
| `LETTERMINT_TRACKING_RECIPIENTS` | `str` | `"plain"` | `"hashed"` stores recipient addresses as a keyed hash |
| `LETTERMINT_TRACKING_HASH_KEY` | `str` | `SECRET_KEY` | Key for `"hashed"` recipients. Changing it makes stored hashes unfindable |
| `LETTERMINT_TRACKING_RETENTION_DAYS` | `int` | `None` | Days `lettermint_prune` keeps; `None` keeps everything |

## Notes

- `LETTERMINT_ROUTE` sets a default route for all messages. Individual messages can override this using `extra_headers["X-Lettermint-Route"]`.
- `LETTERMINT_BULK_ROUTE` applies to `send_bulk()` and `send_bulk_mail()` only, so list mail can go out on a different route than the rest of your email. Like `LETTERMINT_ROUTE` it takes a route slug. The type of that route in Lettermint, `transactional` or `broadcast`, is invisible from here. Precedence, highest first: the message's own `X-Lettermint-Route` header (which is what `route=` on `send_bulk_mail()` sets), the `route=` argument of `send_bulk()`, `LETTERMINT_BULK_ROUTE`, `LETTERMINT_ROUTE`, and finally the default route of your API key.
- `extra_headers["X-Lettermint-Tag"]` sets the Lettermint tag of a message (for example a campaign name). It is stored on `LmEmailMessage.tag` when tracking is installed.
- `LETTERMINT_BASE_URL` is rarely needed. Only set this if you are testing against a custom or staging Lettermint environment.
- `LETTERMINT_TIMEOUT` is a positive number of seconds and covers the whole request, including the response body.
- `LETTERMINT_WEBHOOK_PATH` is read when `lettermint_django.urls` is imported. Include those URLs at the root of your URLconf; the setting is the whole path. Register exactly that path, trailing slash included, in Lettermint.
- `LETTERMINT_WEBHOOK_SECRET` is only read by the webhook view. The view raises `ImproperlyConfigured` when it is missing, so a misconfigured endpoint fails loudly instead of silently rejecting deliveries.
- `LETTERMINT_TRACKING = False` is the way to switch tracking off without losing the admin or orphaning the tables; removing the app from `INSTALLED_APPS` also stops it, but drops both.
- `extra_headers["X-Lettermint-Track"] = "false"` (also `0`, `no`, `off`) keeps a single message out of tracking. The header is not passed on.
- An unknown value for `LETTERMINT_TRACKING_EVENT_DATA`, `LETTERMINT_TRACKING_RECIPIENTS` or `LETTERMINT_TRACKING_RETENTION_DAYS` is reported by system check `lettermint_django.E001`.

## Example

```python
import os

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
LETTERMINT_ROUTE = "app-mail"
LETTERMINT_BULK_ROUTE = "app-lists"
LETTERMINT_TIMEOUT = 10
```
