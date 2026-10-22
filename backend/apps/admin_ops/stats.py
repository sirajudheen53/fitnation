"""Platform-wide stats selectors (issue #47) — cross-tenant, superuser-only.

Builds the payload behind ``GET /api/v1/admin/stats/`` for the operator
cockpit: gym/member/user/device totals, a membership summary, and revenue
series. All aggregates are plain ORM reads — nothing tenant-scoped here (the
permission layer is the isolation boundary).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db.models import Count, DateTimeField, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.access.models import BiometricDevice
from apps.customers.models import Customer
from apps.memberships.models import Membership
from apps.payments.models import Payment
from apps.tenants.models import Tenant
from apps.users.models import User

STATS_MONTHS = 6

STAFF_ROLES = ("gym_owner", "manager", "trainer", "dietitian")


def _last_n_month_starts(n: int = STATS_MONTHS) -> list[date]:
    """The first day of each of the last ``n`` months, oldest first (local tz)."""
    today = timezone.localdate()
    year, month = today.year, today.month
    months: list[date] = []
    for _ in range(n):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return list(reversed(months))


def _month_key(value: date | datetime | str | None) -> str | None:
    """ISO ``YYYY-MM`` key for a date/datetime (strings pass through)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value[:7]
    if isinstance(value, datetime):
        value = timezone.localdate(value)
    return f"{value.year:04d}-{value.month:02d}"


def _month_series_rows(queryset: Any, month_field: str, value_field: str) -> dict[str, Any]:
    """``{YYYY-MM: value}`` from a queryset grouped by calendar month."""
    rows = (
        queryset.annotate(bucket=TruncMonth(month_field, output_field=DateTimeField()))
        .values("bucket")
        .annotate(value=value_field)
        .values_list("bucket", "value")
    )
    return {_month_key(bucket): value for bucket, value in rows}


def _fill_month_series(months: list[date], values: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Zero-fill a per-month series over the stats window, oldest first."""
    return [
        {"month": _month_key(month_start), key: values.get(_month_key(month_start), 0)}
        for month_start in months
    ]


def _first_of_month() -> date:
    """The first day of the current local month."""
    today = timezone.localdate()
    return today.replace(day=1)


def gym_stats(months: list[date]) -> dict[str, Any]:
    """Gym (tenant) totals, lifecycle split, and creation series.

    Returns:
        ``{total, active, trial, suspended, cancelled, archived,
        new_this_month, by_month}`` — ``by_month`` is a zero-filled 6-month
        ``[{month, count}]`` series of new gyms.
    """
    by_month = _month_series_rows(Tenant.objects, "created_at", Count("id"))
    return {
        "total": Tenant.objects.count(),
        "active": Tenant.objects.filter(status=Tenant.Status.ACTIVE).count(),
        "trial": Tenant.objects.filter(status=Tenant.Status.TRIAL).count(),
        "suspended": Tenant.objects.filter(status=Tenant.Status.SUSPENDED).count(),
        "cancelled": Tenant.objects.filter(status=Tenant.Status.CANCELLED).count(),
        "archived": Tenant.objects.filter(status=Tenant.Status.ARCHIVED).count(),
        "new_this_month": Tenant.objects.filter(created_at__date__gte=_first_of_month()).count(),
        "by_month": _fill_month_series(months, by_month, "count"),
    }


def member_stats(months: list[date]) -> dict[str, Any]:
    """Gym member (Customer) totals across the platform.

    Returns:
        ``{total, new_this_month, by_month}`` — ``by_month`` is a zero-filled
        6-month ``[{month, count}]`` series of new members.
    """
    by_month = _month_series_rows(Customer.objects, "created_at", Count("id"))
    return {
        "total": Customer.objects.count(),
        "new_this_month": Customer.objects.filter(created_at__date__gte=_first_of_month()).count(),
        "by_month": _fill_month_series(months, by_month, "count"),
    }


def user_stats() -> dict[str, Any]:
    """All users on the platform, split into gym staff vs. customers."""
    total = User.objects.count()
    staff = User.objects.filter(role__in=STAFF_ROLES).count()
    platform_admins = User.objects.filter(role=User.Role.PLATFORM_ADMIN).count()
    return {
        "total": total,
        "staff": staff,
        "customers": User.objects.filter(role=User.Role.CUSTOMER).count(),
        "platform_admins": platform_admins,
        "new_this_month": User.objects.filter(created_at__date__gte=_first_of_month()).count(),
    }


def membership_stats() -> dict[str, Any]:
    """Membership summary by stored lifecycle status."""
    by_status = {
        row["status"]: row["count"]
        for row in Membership.objects.values("status").annotate(count=Count("id")).values("status", "count")
    }
    return {
        "total": sum(by_status.values()),
        "active": by_status.get("active", 0),
        "expired": by_status.get("expired", 0),
        "cancelled": by_status.get("cancelled", 0),
    }


def device_stats() -> dict[str, Any]:
    """Biometric access devices registered across gyms."""
    return {
        "total": BiometricDevice.objects.count(),
        "active": BiometricDevice.objects.filter(is_active=True).count(),
    }


def revenue_stats(months: list[date]) -> dict[str, Any]:
    """Payment/revenue summary across the platform.

    Completed payments are "collected"; the monthly series buckets each
    payment into its ``paid_at`` month (falling back to ``created_at`` for
    rows completed without a timestamp).
    """
    completed = Payment.objects.filter(status=Payment.Status.COMPLETED)
    bucket_expr = Coalesce("paid_at", "created_at", output_field=DateTimeField())
    by_month_rows = (
        completed.annotate(bucket=TruncMonth(bucket_expr, output_field=DateTimeField()))
        .values("bucket")
        .annotate(total=Sum("amount"))
        .values_list("bucket", "total")
    )
    by_month = {_month_key(bucket): total for bucket, total in by_month_rows}
    zero_filled = [
        {"month": _month_key(month_start), "total": by_month.get(_month_key(month_start), Decimal("0.00"))}
        for month_start in months
    ]
    return {
        "data_available": Payment.objects.exists(),
        "total_collected": completed.aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        "collected_this_month": completed.filter(
            paid_at__date__gte=_first_of_month(),
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00"),
        "pending_amount": Payment.objects.filter(status=Payment.Status.PENDING).aggregate(total=Sum("amount"))[
            "total"
        ]
        or Decimal("0.00"),
        "failed_count": Payment.objects.filter(status=Payment.Status.FAILED).count(),
        "by_month": zero_filled,
    }


def platform_stats() -> dict[str, Any]:
    """Assemble the full ``GET /api/v1/admin/stats/`` payload.

    Returns:
        The mapping consumed by ``PlatformStatsSerializer`` — see its
        field docs for the documented response shape.
    """
    months = _last_n_month_starts()
    gyms = gym_stats(months)
    members = member_stats(months)
    return {
        "gyms": gyms,
        "members": members,
        "users": user_stats(),
        "memberships": membership_stats(),
        "devices": device_stats(),
        "revenue": revenue_stats(months),
        "window_months": STATS_MONTHS,
        "growth": {
            # Chart-ready aliases of the by_month series (issue scope names
            # growth explicitly); same list objects, no re-computation.
            "new_gyms_by_month": gyms["by_month"],
            "new_members_by_month": members["by_month"],
        },
    }
