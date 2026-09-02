"""Persistence helpers behind the email backend and the webhook view.

Every function here is a no-op when ``lettermint_django`` is not in
``INSTALLED_APPS``, so the email backend can call them unconditionally.
Models are imported lazily for the same reason.
"""

from .enabled import is_tracking_enabled
from .record_event import record_event
from .record_sent import record_sent

__all__ = ["is_tracking_enabled", "record_event", "record_sent"]
