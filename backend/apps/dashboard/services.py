"""Dashboard aggregation services (FBOS-008).

These functions pull from the customers, memberships, payments, attendance and
trainers apps and shape the data for the ERP dashboard. Each aggregation is
tenant-scoped via ``Model.objects.for_tenant(tenant)`` and always returns
well-formed defaults (zeros / empty lists) rather than raising on empty data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count
from django.db.models.functions import ExtractHour
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.customers.models import Customer
from apps.dashboard.models import DashboardCache
from apps.memberships.models import Membership
from apps.payments.models import Payment
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.users.models import User


def get_overview(tenant: Any) -> dict:
    """Return the top-level dashboard overview for a tenant.

    Composes total members, active memberships, revenue summary, today's
    attendance, trainer count and pending payments.
    """
    cached = _read(tenant, "overview")
    if cached is not None:
        return cached

    today = timezone.localdate()

    total_members = Customer.objects.for_tenant(tenant).count()
    active_memberships = Membership.objects.for_tenant(tenant).filter(
        status=Membership.Status.ACTIVE
    ).count()

    # Revenue summary (completed payments only).
    paid_qs = Payment.objects.for_tenant(tenant).filter(
        status=Payment.Status.COMPLETED
    )
    total_revenue = _sum(paid_qs.values_list("amount", flat=True))
    month_start = timezone.make_aware(
        datetime.combine(today.replace(day=1), datetime.min.time())
    )
    this_month = _sum(
        paid_qs.filter(paid_at__gte=month_start).values_list("amount", flat=True)
    )

    today_attendance = AttendanceRecord.objects.for_tenant(tenant).filter(
        date=today
    ).count()

    trainer_count = User.objects.filter(
        tenant=tenant, role=User.Role.TRAINER, trainer_profile__isnull=False
    ).count()

    pending_payments = Payment.objects.for_tenant(tenant).filter(
        status=Payment.Status.PENDING
    ).count()

    data = {
        "total_members": total_members,
        "active_memberships": active_memberships,
        "revenue_summary": {
            "total": round(float(total_revenue), 2),
            "this_month": round(float(this_month), 2),
        },
        "today_attendance": today_attendance,
        "trainer_count": trainer_count,
        "pending_payments": pending_payments,
    }
    _write(tenant, "overview", data)
    return data


def get_revenue_breakdown(tenant: Any, period: str = "monthly") -> dict:
    """Return a revenue time-series from completed payments.

    ``period`` is one of ``daily``, ``weekly``, ``monthly``. Each bucket is keyed
    by an ISO date string and holds the summed completed revenue for that bucket.
    """
    if period not in {"daily", "weekly", "monthly"}:
        period = "monthly"

    paid = (
        Payment.objects.for_tenant(tenant)
        .filter(status=Payment.Status.COMPLETED, paid_at__isnull=False)
    )

    buckets: dict[str, Decimal] = {}
    for payment in paid.iterator(chunk_size=500):
        day = timezone.localtime(payment.paid_at).date()
        key = _bucket_key(day, period)
        buckets[key] = buckets.get(key, Decimal(0)) + payment.amount

    series = [
        {"period": key, "amount": round(float(amount), 2)}
        for key, amount in sorted(buckets.items())
    ]
    return {"period": period, "results": series}


def _bucket_key(day: Any, period: str) -> str:
    """Map a date into a bucket label for the given period."""
    if period == "daily":
        return day.isoformat()
    if period == "weekly":
        week_start = day - timedelta(days=day.weekday())
        return week_start.isoformat()
    return day.replace(day=1).isoformat()


def get_attendance_analytics(tenant: Any) -> dict:
    """Return attendance analytics: peak hours and weekly check-in counts."""
    qs = AttendanceRecord.objects.for_tenant(tenant)

    # Peak hours: check-ins bucketed by local hour of check_in_time.
    peak_qs = (
        qs.annotate(hour=ExtractHour("check_in_time"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("-count", "hour")
    )
    peak_hours = [
        {"hour": int(row["hour"] or 0), "count": row["count"]}
        for row in peak_qs
    ]

    # Weekly counts: bucket by ISO week start date.
    weekly: dict[str, int] = {}
    for row in qs.values_list("check_in_time", flat=True).iterator(chunk_size=500):
        day = timezone.localtime(row).date()
        week_start = day - timedelta(days=day.weekday())
        weekly[week_start.isoformat()] = weekly.get(week_start.isoformat(), 0) + 1

    weekly_counts = [
        {"week": key, "count": value}
        for key, value in sorted(weekly.items())
    ]

    return {
        "peak_hours": peak_hours,
        "weekly_counts": weekly_counts,
    }


def get_membership_stats(tenant: Any) -> dict:
    """Return membership status counts and per-plan distribution."""
    qs = Membership.objects.for_tenant(tenant)

    counts = {
        "active": qs.filter(status=Membership.Status.ACTIVE).count(),
        "expired": qs.filter(status=Membership.Status.EXPIRED).count(),
        "cancelled": qs.filter(status=Membership.Status.CANCELLED).count(),
    }

    plan_distribution = list(
        qs.values("plan__name", "plan__plan_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    plan_distribution = [
        {
            "plan": row["plan__name"],
            "plan_type": row["plan__plan_type"],
            "count": row["count"],
        }
        for row in plan_distribution
    ]

    return {
        "status_counts": counts,
        "plan_distribution": plan_distribution,
    }


def get_trainer_performance(tenant: Any) -> dict:
    """Return top trainers ranked by revenue, rating and client count.

    Combines per-month ``TrainerPerformance`` snapshots with live
    ``TrainerAssignment`` counts to give a rounded performance view.
    """
    perf = TrainerPerformance.objects.for_tenant(tenant)
    assignments = TrainerAssignment.objects.for_tenant(tenant).filter(
        is_active=True
    )

    revenue_by_trainer: dict[int, Decimal] = {}
    rating_by_trainer: dict[int, Decimal] = {}
    sessions_by_trainer: dict[int, int] = {}
    for row in perf.values("trainer_id", "revenue", "rating_avg", "sessions_completed"):
        tid = row["trainer_id"]
        revenue_by_trainer[tid] = revenue_by_trainer.get(tid, Decimal(0)) + row["revenue"]
        if row["rating_avg"] is not None:
            current = rating_by_trainer.get(tid)
            rating_by_trainer[tid] = max(current or Decimal(0), row["rating_avg"])
        sessions_by_trainer[tid] = sessions_by_trainer.get(tid, 0) + (
            row["sessions_completed"] or 0
        )

    client_count_by_trainer: dict[int, int] = {}
    for row in assignments.values("trainer_id").annotate(count=Count("id")):
        client_count_by_trainer[row["trainer_id"]] = row["count"]

    trainer_ids = set(revenue_by_trainer) | set(client_count_by_trainer)
    names = {
        t.id: (t.user.get_full_name() or t.user.email)
        for t in User.objects.filter(
            id__in=trainer_ids, trainer_profile__isnull=False
        ).select_related("trainer_profile", "trainer_profile__user")
    } if trainer_ids else {}

    rows = []
    for tid in trainer_ids:
        rows.append(
            {
                "trainer_id": tid,
                "name": names.get(tid, f"Trainer #{tid}"),
                "revenue": round(float(revenue_by_trainer.get(tid, Decimal(0))), 2),
                "rating_avg": (
                    round(float(rating_by_trainer[tid]), 2)
                    if tid in rating_by_trainer
                    else None
                ),
                "client_count": client_count_by_trainer.get(tid, 0),
                "sessions_completed": sessions_by_trainer.get(tid, 0),
            }
        )

    rows.sort(key=lambda r: (r["revenue"], r["client_count"]), reverse=True)
    return {"results": rows, "total": len(rows)}


def _sum(values: Any) -> Decimal:
    """Sum an iterable of Decimal amounts safely, returning Decimal zero on empty."""
    total = Decimal(0)
    for value in values:
        try:
            total += Decimal(value or 0)
        except (TypeError, ValueError):
            continue
    return total


def _read(tenant: Any, name: str) -> dict | None:
    """Read a cached metric for the tenant, if fresh."""
    try:
        cache = (
            DashboardCache.objects.for_tenant(tenant)
            .filter(metric_name=name)
            .order_by("-date")
            .first()
        )
        if cache is not None and cache.date >= timezone.localdate():
            return cache.metric_value
    except DashboardCache.DoesNotExist:
        pass
    return None


def _write(tenant: Any, name: str, value: dict) -> None:
    """Write/refresh a cached metric value for the tenant for today."""
    DashboardCache.objects.update_or_create(
        tenant=tenant,
        metric_name=name,
        date=timezone.localdate(),
        defaults={"metric_value": value, "auto_updated": True},
    )
