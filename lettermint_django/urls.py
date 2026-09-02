"""URL patterns for the Lettermint webhook endpoint.

Include these in your project's ``urls.py``::

    path("lettermint/", include("lettermint_django.urls")),

and point the webhook in the Lettermint dashboard to
``https://example.com/lettermint/message-events/``.
"""

from django.urls import path

from .views import message_events

urlpatterns = [
    path("message-events/", message_events, name="lm-message-events"),
]
