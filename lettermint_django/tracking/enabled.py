"""Whether the tracking app is installed."""

from django.apps import apps

APP_NAME = "lettermint_django"


def is_tracking_enabled():
    """True when ``lettermint_django`` is in ``INSTALLED_APPS``."""
    return apps.is_installed(APP_NAME)
