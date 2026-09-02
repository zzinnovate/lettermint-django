"""``resolve_webhook_url()``: where the webhook is served, or ``None`` when it is not included."""

from django.urls import NoReverseMatch, reverse


def resolve_webhook_url() -> str | None:
    """Return the URL of ``lm-message-events``, or ``None`` if the URLs are not included."""
    try:
        return reverse("lm-message-events")
    except NoReverseMatch:
        return None
    except Exception:  # pragma: no cover - a broken URLconf is reported by Django's own checks
        return None
