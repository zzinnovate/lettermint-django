"""Shared admin behaviour."""

from email.utils import parseaddr

from django.utils.text import smart_split, unescape_string_literal

from ..tracking.privacy_settings import recipient_mode
from ..tracking.store_address import store_address


class ReadOnlyMixin:
    """Disallow adding and editing; records are written by the backend and webhook only."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class HashedRecipientSearchMixin:
    """Let the admin search find hashed recipients by their plain address.

    With ``LETTERMINT_TRACKING_RECIPIENTS = "hashed"`` every search term that is
    a complete email address is replaced by its hash before the normal search
    runs, so typing ``ann@example.com`` finds her rows. Other terms, and partial
    addresses such as ``@example.com``, are searched as typed.
    """

    def get_search_results(self, request, queryset, search_term):
        if recipient_mode() == "hashed" and search_term:
            search_term = " ".join(_hash_if_address(term) for term in smart_split(search_term))
        return super().get_search_results(request, queryset, search_term)


def _hash_if_address(term):
    if term.startswith(('"', "'")) and term[0] == term[-1]:
        term = unescape_string_literal(term)
    _name, address = parseaddr(term)
    local, _, domain = address.partition("@")
    if local and domain:
        return store_address(address)
    return f'"{term}"' if " " in term else term
