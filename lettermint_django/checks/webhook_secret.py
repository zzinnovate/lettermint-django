"""``lettermint_django.W002``: the webhook is served but ``LETTERMINT_WEBHOOK_SECRET`` is empty."""

from django.conf import settings
from django.core.checks import Tags, Warning, register

from .resolve_webhook_url import resolve_webhook_url


@register(Tags.security)
def check_webhook_secret(app_configs, **kwargs):
    """Warn when the webhook URL is included without a signing secret.

    The view refuses every delivery with a 500 in that case (it never accepts
    unsigned requests), but you would only find out at the first delivery.
    """
    url = resolve_webhook_url()
    if url is None:
        return []  # Webhook URLs not included; nothing to secure.
    secret = getattr(settings, "LETTERMINT_WEBHOOK_SECRET", None)
    if isinstance(secret, str) and secret.strip():
        return []
    return [
        Warning(
            f"The Lettermint webhook is served at {url} but LETTERMINT_WEBHOOK_SECRET is not set; "
            "every delivery will be rejected.",
            hint="Copy the signing secret of the webhook from the Lettermint dashboard into LETTERMINT_WEBHOOK_SECRET.",
            id="lettermint_django.W002",
        )
    ]
