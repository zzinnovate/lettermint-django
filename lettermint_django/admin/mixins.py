"""Shared admin behaviour."""


class ReadOnlyMixin:
    """Disallow adding and editing; records are written by the backend and webhook only."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
