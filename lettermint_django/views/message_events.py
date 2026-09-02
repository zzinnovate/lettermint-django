"""``message_events``: webhook endpoint that receives message events from Lettermint.

Signature verification is done by the Lettermint SDK (HMAC-SHA256 with a
timestamp tolerance). Verified events are stored via
:func:`lettermint_django.tracking.record_event`.
"""

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from lettermint import Webhook, WebhookVerificationError

from ..tracking import record_event

logger = logging.getLogger("lettermint_django")


def get_webhook_secret():
    secret = getattr(settings, "LETTERMINT_WEBHOOK_SECRET", None)
    if isinstance(secret, str):
        secret = secret.strip()
    if not secret:
        raise ImproperlyConfigured(
            "LETTERMINT_WEBHOOK_SECRET must be set to receive Lettermint webhooks."
        )
    return secret


@csrf_exempt
@require_POST
def message_events(request):
    """Verify a Lettermint webhook delivery and store the event.

    Responds ``400`` when the signature, timestamp or JSON body is invalid, and
    ``200`` otherwise. ``webhook.test``, ``message.inbound`` and events without
    a ``data.message_id`` (suppression events) are acknowledged without being
    stored; the JSON response says ``"stored": false`` for them.
    """
    secret = get_webhook_secret()

    try:
        body = request.body.decode("utf-8")
    except UnicodeDecodeError:
        return HttpResponseBadRequest("Webhook body must be UTF-8 encoded JSON.")

    try:
        payload = Webhook(secret).verify_headers(dict(request.headers), body)
    except WebhookVerificationError as exc:
        logger.warning("Rejected Lettermint webhook: %s", exc)
        return HttpResponseBadRequest("Invalid webhook signature.")

    if not isinstance(payload, dict):
        return HttpResponseBadRequest("Webhook body must be a JSON object.")

    if payload.get("event") == "webhook.test":
        return JsonResponse({"received": True, "stored": False})

    event, created = record_event(payload)
    return JsonResponse({"received": True, "stored": created})
