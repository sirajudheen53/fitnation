"""Daily membership-expiry nudges (FBOS-011 brief, deliverable 7).

The WATI ``membership_expiry`` template already exists and the post_save
signal covers memberships saved near expiry; this command is the daily sweep
for every live membership whose end_date falls inside the window (cron/Cloud
Scheduler driven — this project has no Celery). Customers who already
received a nudge today are skipped, so re-running the command is safe.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.memberships.models import Membership
from apps.notifications.models import NotificationLog
from apps.notifications.services.wati_service import send_notification


class Command(BaseCommand):
    """Send expiry-reminder WhatsApp messages for memberships ending soon."""

    help = "Send membership-expiry nudges for live memberships ending within --days."

    def add_arguments(self, parser) -> None:
        """Add the --days window flag.

        Args:
            parser: The argparse parser.
        """
        parser.add_argument("--days", type=int, default=7, help="Notify memberships ending within this many days.")

    def handle(self, *args: object, **options: object) -> None:
        """Sweep and send; print a one-line summary."""
        days = int(options["days"])
        today = timezone.localdate()
        window_end = today + timedelta(days=days)
        day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        memberships = (
            Membership.objects.exclude(status=Membership.Status.CANCELLED)
            .filter(end_date__gte=today, end_date__lte=window_end)
            .select_related("customer", "plan", "tenant")
        )
        sent = skipped = 0
        notified = set(
            NotificationLog.objects.filter(
                notification_type=NotificationLog.NotificationType.MEMBERSHIP_EXPIRY,
                created_at__gte=day_start,
            ).values_list("customer_id", flat=True)
        )
        for membership in memberships:
            if membership.customer_id in notified:
                skipped += 1
                continue
            log = send_notification(
                membership.tenant,
                membership.customer,
                NotificationLog.NotificationType.MEMBERSHIP_EXPIRY,
                {
                    "customer_name": membership.customer.name,
                    "expiry_date": membership.end_date.isoformat(),
                },
            )
            if log.status == NotificationLog.Status.SENT:
                sent += 1
            else:
                skipped += 1
            notified.add(membership.customer_id)
        self.stdout.write(f"membership expiry nudges: {sent} sent, {skipped} skipped/not-configured")
