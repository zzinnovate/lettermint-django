"""``message_events``: webhook endpoint that receives message events from Lettermint.

Signature verification is done by the Lettermint SDK (HMAC-SHA256 over the
raw body with a timestamp tolerance; both ``X-Lettermint-Signature`` and
``X-Lettermint-Delivery`` are required). Verified events are stored via
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

#: ``WebhookVerificationError.reason`` values that blame the body, not the signature.
BODY_REASONS = frozenset({"body_invalid", "payload_invalid"})


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
        payload = Webhook(secret).verify(request.body, request.headers)
    except WebhookVerificationError as exc:
        logger.warning("Rejected Lettermint webhook (%s): %s", exc.reason, exc)
        if exc.reason in BODY_REASONS:
            return HttpResponseBadRequest("Webhook body must be a JSON object.")
        return HttpResponseBadRequest("Invalid webhook signature.")

    if payload.get("event") == "webhook.test":
        return JsonResponse({"received": True, "stored": False})

    event, created = record_event(payload)
    return JsonResponse({"received": True, "stored": created})
