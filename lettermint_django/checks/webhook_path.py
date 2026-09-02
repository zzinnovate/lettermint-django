"""``lettermint_django.W001``: the webhook URL does not match ``LETTERMINT_WEBHOOK_PATH``."""

from django.core.checks import Tags, Warning, register

from .resolve_webhook_url import resolve_webhook_url


@register(Tags.urls)
def check_webhook_path(app_configs, **kwargs):
    """Warn when ``lettermint_django.urls`` is included under a prefix.

    The path in ``LETTERMINT_WEBHOOK_PATH`` is meant to be the whole path, so
    an include such as ``path("lettermint/", include("lettermint_django.urls"))``
    silently doubles it and Lettermint's deliveries end in a 404.
    """
    from ..urls import get_webhook_path

    actual = resolve_webhook_url()
    if actual is None:
        return []  # Webhook URLs not included; a backend-only project.
    expected = "/" + get_webhook_path()
    if actual == expected:
        return []
    return [
        Warning(
            f"The Lettermint webhook resolves to {actual}, but LETTERMINT_WEBHOOK_PATH makes it {expected}.",
            hint=(
                'Include the webhook URLs at the root: path("", include("lettermint_django.urls")). '
                "Change LETTERMINT_WEBHOOK_PATH to move the endpoint."
            ),
            id="lettermint_django.W001",
        )
    ]
