# Installation

## Requirements

- Python 3.11+ (Django 6 requires Python 3.12+)
- Django 4.2, 5.x, or 6.x
- [lettermint](https://github.com/lettermint/lettermint-python) 2.0+

## Install

```bash
pip install lettermint-django
```

## Setup: Backend Only

If you only need to send emails through Lettermint, no `INSTALLED_APPS` entry is needed. Just configure the backend in your settings:

```python
EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = "lm_..."
```

No migrations required.

## Setup: With Email Tracking

To track delivery status and bounces, add `lettermint_django` to `INSTALLED_APPS`, set the webhook secret and run migrations:

```python
INSTALLED_APPS = [
    # ...
    "lettermint_django",
]

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = "lm_..."
LETTERMINT_WEBHOOK_SECRET = "..."  # signing secret from the Lettermint dashboard
```

```bash
python manage.py migrate lettermint_django
```

This creates the `LmEmailMessage` and `LmEmailEvent` tables. Then include `lettermint_django.urls` in your project and register the webhook in Lettermint; see the [Tracking guide](tracking.md) for the full setup.

## From source

```bash
git clone https://github.com/zzinnovate/lettermint-django.git
cd lettermint-django

# Install with development dependencies
pip install -e ".[dev]"
```

## Verify

```python
import lettermint_django
print(lettermint_django.__version__)
```

If you see a version string, the package is installed correctly.
