# Configuration

Add two settings to your Django settings file to get started.

## Minimal setup

```python
import os

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
```

No `INSTALLED_APPS` entry is needed for sending emails. Add `lettermint_django` to `INSTALLED_APPS` only when you want [email tracking](tracking.md).

## Environment variable

Store your API key in an environment variable, never hard-code it:

```bash
# .env or shell
LETTERMINT_API_KEY=lm_your_api_key_here
```

## Full settings example

```python
import os

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
LETTERMINT_ROUTE = os.getenv("LETTERMINT_ROUTE", "transactional")  # optional default route
LETTERMINT_TIMEOUT = 10  # optional, seconds
LETTERMINT_WEBHOOK_SECRET = os.getenv("LETTERMINT_WEBHOOK_SECRET")  # only with tracking
```

See the [Settings reference](../reference/settings.md) for all available options.

## Per-environment configuration

For development you may want to use Django's built-in file-based backend instead:

```python
# settings/development.py
if os.getenv("LETTERMINT_API_KEY"):
    EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
    LETTERMINT_API_KEY = os.getenv("LETTERMINT_API_KEY")
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / "tmp" / "email"
```
