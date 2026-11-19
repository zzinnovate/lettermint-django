"""``manage.py lettermint_prune``: delete tracking rows older than the retention."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ...tracking.privacy_settings import retention_days


class Command(BaseCommand):
    help = (
        "Delete tracked messages created, and webhook events that occurred, more than N days ago. "
        "N is --days, else LETTERMINT_TRACKING_RETENTION_DAYS."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, help="Keep this many days; overrides LETTERMINT_TRACKING_RETENTION_DAYS.")
        parser.add_argument("--dry-run", action="store_true", help="Count what would be deleted, delete nothing.")

    def handle(self, *args, days=None, dry_run=False, **options):
        if days is None:
            days = retention_days()
        if days is None:
            self.stdout.write("No retention set: pass --days or set LETTERMINT_TRACKING_RETENTION_DAYS. Nothing deleted.")
            return
        if days < 1:
            raise CommandError("--days must be at least 1.")

        from ...models import LmEmailEvent, LmEmailMessage

        cutoff = timezone.now() - timedelta(days=days)
        messages = LmEmailMessage.objects.filter(created_at__lt=cutoff)
        # Events of an old message go with it, however recent; events of messages
        # this app never recorded go by their own age.
        events = LmEmailEvent.objects.filter(Q(email_message__created_at__lt=cutoff) | Q(occurred_at__lt=cutoff))

        if dry_run:
            self.stdout.write(
                f"Would delete {messages.count()} messages and {events.count()} events older than {days} days."
            )
            return

        with transaction.atomic():
            # Events first: the foreign key is SET_NULL, so deleting the messages
            # first would detach their events instead of removing them.
            event_count = events.delete()[0]
            message_count = messages.delete()[0]
        self.stdout.write(f"Deleted {message_count} messages and {event_count} events older than {days} days.")
