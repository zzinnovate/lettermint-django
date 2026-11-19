"""``store_address()``: the form in which a recipient address is stored."""

import hashlib
import hmac
from email.utils import parseaddr

from django.conf import settings

from .privacy_settings import recipient_mode


def store_address(address: object) -> str:
    """Return ``address`` as tracking stores it.

    With ``LETTERMINT_TRACKING_RECIPIENTS = "plain"`` that is the address
    unchanged. With ``"hashed"`` it is the hex HMAC-SHA256 of the bare address,
    display name dropped, trimmed and lowercased, keyed with
    ``LETTERMINT_TRACKING_HASH_KEY`` (falling back to ``SECRET_KEY``). The same
    address always gives the same hash for the same key, so lookups work;
    a changed key finds nothing stored under the old one.
    """
    text = str(address or "")
    if recipient_mode() != "hashed" or not text.strip():
        return text
    _name, bare = parseaddr(text)
    normalized = (bare or text).strip().lower()
    key = getattr(settings, "LETTERMINT_TRACKING_HASH_KEY", None) or settings.SECRET_KEY
    return hmac.new(str(key).encode(), normalized.encode(), hashlib.sha256).hexdigest()
