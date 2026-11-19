"""``lettermint_django.E001``: a tracking privacy setting has a value this package does not know."""

from django.core.checks import Error, Tags, register
from django.core.exceptions import ImproperlyConfigured

from ..tracking.privacy_settings import event_data_mode, recipient_mode, retention_days


@register(Tags.compatibility)
def check_tracking_settings(app_configs, **kwargs):
    """Report invalid privacy settings at startup instead of at the first send or webhook.

    A typo would otherwise surface as a logged tracking failure on every send
    and a ``5xx`` (and retries) on every webhook delivery.
    """
    errors = []
    for reader in (event_data_mode, recipient_mode, retention_days):
        try:
            reader()
        except ImproperlyConfigured as exc:
            errors.append(Error(str(exc), id="lettermint_django.E001"))
    return errors
