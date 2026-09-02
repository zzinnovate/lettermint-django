"""URL patterns for the Lettermint webhook endpoint.

Include them at the root of your project's ``urls.py``::

    path("", include("lettermint_django.urls")),

The endpoint is then ``POST /lettermint/message-events/`` by default. Set
``LETTERMINT_WEBHOOK_PATH`` (for example ``"lmnt/events/"``) to change the
whole path, and register exactly that URL in the Lettermint dashboard.
``reverse("lm-message-events")`` returns the configured path.
"""

from django.conf import settings
from django.urls import path

from .views import message_events

DEFAULT_WEBHOOK_PATH = "lettermint/message-events/"


def get_webhook_path() -> str:
    """The configured webhook path without a leading slash, e.g. ``lettermint/message-events/``."""
    value = getattr(settings, "LETTERMINT_WEBHOOK_PATH", None)
    value = str(value).strip() if value else ""
    return (value or DEFAULT_WEBHOOK_PATH).lstrip("/")


urlpatterns = [
    path(get_webhook_path(), message_events, name="lm-message-events"),
]
