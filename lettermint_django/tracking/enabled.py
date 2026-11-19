"""Whether tracking is on: the app is installed and ``LETTERMINT_TRACKING`` is not ``False``."""

from django.apps import apps
from django.conf import settings

APP_NAME = "lettermint_django"


def is_tracking_enabled():
    """True when ``lettermint_django`` is in ``INSTALLED_APPS`` and ``LETTERMINT_TRACKING`` is truthy.

    With the setting off the models, admin and webhook URL stay; nothing new is
    stored and the webhook still acknowledges every delivery.
    """
    return apps.is_installed(APP_NAME) and bool(getattr(settings, "LETTERMINT_TRACKING", True))
