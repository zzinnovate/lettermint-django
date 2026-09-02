"""Admin for ``LmEmailEvent``, plus the inline used on the message admin."""

from django.contrib import admin

from ..models import LmEmailEvent
from .mixins import ReadOnlyMixin


class LmEmailEventInline(ReadOnlyMixin, admin.TabularInline):
    model = LmEmailEvent
    fields = ("occurred_at", "event", "recipient", "reason_code", "reason")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ("-occurred_at",)


@admin.register(LmEmailEvent)
class LmEmailEventAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("occurred_at", "event", "recipient", "message_id", "reason_code")
    list_filter = ("event",)
    search_fields = ("event_id", "message_id", "recipient", "reason", "reason_code")
    readonly_fields = [field.name for field in LmEmailEvent._meta.fields]
    date_hierarchy = "occurred_at"
    raw_id_fields = ("email_message",)
