"""Admin for ``LmEmailMessage``."""

from django.contrib import admin

from ..models import LmEmailMessage
from .lm_email_event import LmEmailEventInline
from .mixins import ReadOnlyMixin


@admin.register(LmEmailMessage)
class LmEmailMessageAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("message_id", "subject", "recipients", "status", "tag", "status_changed_at", "created_at")
    list_filter = ("status", "route", "tag")
    search_fields = ("message_id", "bulk_id", "subject", "from_email", "to", "events__recipient")
    readonly_fields = [field.name for field in LmEmailMessage._meta.fields]
    date_hierarchy = "created_at"
    inlines = [LmEmailEventInline]

    @admin.display(description="To")
    def recipients(self, obj):
        return ", ".join(obj.to or [])
