"""Minimal Django settings for the test suite."""

SECRET_KEY = "test-secret-key-for-lettermint-django"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"
LETTERMINT_API_KEY = "lm_test_key"
DEFAULT_FROM_EMAIL = "Test <noreply@example.com>"
SITE_NAME = "Test Site"
