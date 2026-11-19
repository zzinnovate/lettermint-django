"""Readers for the settings that decide how much tracking stores."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

EVENT_DATA_MODES = ("full", "minimal", "none")
RECIPIENT_MODES = ("plain", "hashed")


def store_subject() -> bool:
    """``LETTERMINT_TRACKING_SUBJECT``: store subjects (default ``True``)."""
    return bool(getattr(settings, "LETTERMINT_TRACKING_SUBJECT", True))


def track_unknown_messages() -> bool:
    """``LETTERMINT_TRACK_UNKNOWN_MESSAGES``: store events of messages this app did not record."""
    return bool(getattr(settings, "LETTERMINT_TRACK_UNKNOWN_MESSAGES", True))


def event_data_mode() -> str:
    """``LETTERMINT_TRACKING_EVENT_DATA``: ``"full"`` (default), ``"minimal"`` or ``"none"``."""
    return _choice("LETTERMINT_TRACKING_EVENT_DATA", EVENT_DATA_MODES)


def recipient_mode() -> str:
    """``LETTERMINT_TRACKING_RECIPIENTS``: ``"plain"`` (default) or ``"hashed"``."""
    return _choice("LETTERMINT_TRACKING_RECIPIENTS", RECIPIENT_MODES)


def retention_days() -> int | None:
    """``LETTERMINT_TRACKING_RETENTION_DAYS``: days to keep tracking rows, ``None`` for ever."""
    value = getattr(settings, "LETTERMINT_TRACKING_RETENTION_DAYS", None)
    if value is None:
        return None
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = 0
    if days < 1 or isinstance(value, bool):
        raise ImproperlyConfigured(
            f"LETTERMINT_TRACKING_RETENTION_DAYS must be a positive number of days or None, got {value!r}."
        )
    return days


def _choice(name: str, choices: tuple[str, ...]) -> str:
    value = getattr(settings, name, choices[0])
    if value not in choices:
        raise ImproperlyConfigured(f"{name} must be one of {', '.join(map(repr, choices))}, got {value!r}.")
    return value
