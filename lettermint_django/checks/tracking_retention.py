"""``lettermint_django.W003``: tracking stores personal data without a retention."""

from django.core.checks import Tags, Warning, register

from ..tracking.enabled import is_tracking_enabled
from ..tracking.privacy_settings import retention_days


@register(Tags.security, deploy=True)
def check_tracking_retention(app_configs, **kwargs):
    """Warn at ``check --deploy`` when tracking is on and nothing is ever pruned.

    Tracked messages and events hold recipient addresses and, by default,
    subjects. Without ``LETTERMINT_TRACKING_RETENTION_DAYS`` they are kept for ever.
    """
    if not is_tracking_enabled() or retention_days() is not None:
        return []
    return [
        Warning(
            "Lettermint tracking keeps recipient addresses and subjects for ever: "
            "LETTERMINT_TRACKING_RETENTION_DAYS is not set.",
            hint="Set LETTERMINT_TRACKING_RETENTION_DAYS and run `manage.py lettermint_prune` daily.",
            id="lettermint_django.W003",
        )
    ]
