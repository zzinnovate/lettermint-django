# Settings Reference

All settings are read from your Django settings module.

## Required

| Setting | Type | Description |
|---|---|---|
| `LETTERMINT_API_KEY` | `str` | Your project API token from the Lettermint dashboard |

## Optional

| Setting | Type | Default | Description |
|---|---|---|---|
| `LETTERMINT_BASE_URL` | `str` | SDK default | Override the Lettermint API base URL |
| `LETTERMINT_ROUTE` | `str` | `None` | Default route applied to all outgoing emails |
| `LETTERMINT_TIMEOUT` | `int` | SDK default | Request timeout in seconds |
| `LETTERMINT_WEBHOOK_SECRET` | `str` | `None` | Signing secret of your Lettermint webhook. Required by the webhook endpoint when [tracking](../getting-started/tracking.md) is installed |

## Notes

- `LETTERMINT_ROUTE` sets a default route for all messages. Individual messages can override this using `extra_headers["X-Lettermint-Route"]`.
- `LETTERMINT_BASE_URL` is rarely needed. Only set this if you are testing against a custom or staging Lettermint environment.
- `LETTERMINT_TIMEOUT` accepts any value accepted by the underlying `lettermint` SDK (integer seconds).
- `LETTERMINT_WEBHOOK_SECRET` is only read by the webhook view. The view raises `ImproperlyConfigured` when it is missing, so a misconfigured endpoint fails loudly instead of silently rejecting deliveries. Tracking itself has no on/off setting: it is active whenever `lettermint_django` is in `INSTALLED_APPS`.

## Example

```python
import os

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
LETTERMINT_ROUTE = "transactional"
LETTERMINT_TIMEOUT = 10
```
