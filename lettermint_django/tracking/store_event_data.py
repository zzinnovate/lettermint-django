"""``store_event_data()``: the part of a webhook's ``data`` object that is stored."""

from collections.abc import Mapping
from typing import Any

from .privacy_settings import event_data_mode, recipient_mode, store_subject
from .store_address import store_address

#: Keys kept by ``LETTERMINT_TRACKING_EVENT_DATA = "minimal"``.
MINIMAL_KEYS = ("message_id", "tag", "tags", "reason", "reason_code")


def store_event_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return what ``LmEmailEvent.data`` stores of a webhook's ``data`` object.

    ``"full"`` keeps everything, minus the subject when
    ``LETTERMINT_TRACKING_SUBJECT`` is off and with the recipient hashed when
    ``LETTERMINT_TRACKING_RECIPIENTS`` is ``"hashed"``. ``"minimal"`` keeps
    :data:`MINIMAL_KEYS` and ``response.enhanced_status_code``. ``"none"``
    keeps nothing.
    """
    mode = event_data_mode()
    if mode == "none":
        return {}
    if mode == "minimal":
        stored = {key: data[key] for key in MINIMAL_KEYS if key in data}
        response = data.get("response")
        if isinstance(response, Mapping) and "enhanced_status_code" in response:
            stored["response"] = {"enhanced_status_code": response["enhanced_status_code"]}
        return stored
    stored = dict(data)
    if not store_subject():
        stored.pop("subject", None)
    if recipient_mode() == "hashed" and "recipient" in stored:
        stored["recipient"] = store_address(stored["recipient"])
    return stored
