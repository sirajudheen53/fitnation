"""Dashboard aggregation services (FBOS-008).

These functions pull from the customers, memberships, payments, attendance and
trainers apps and shape the data for the ERP dashboard. Each aggregation is
tenant-scoped via ``Model.objects.for_tenant(tenant)`` and always returns
well-formed defaults (zeros / empty lists) rather than raising on empty data.
"""

from __future__ import annotations

import datetime as dt
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
    # Reject cached payloads from before the "mrr" field was added to the
    # contract — otherwise a same-day cache row would serve the old shape.
    if cached is not None and isinstance(cached, dict) and "mrr" in cached:
        return cached

    today = timezone.localdate()

    total_members = Customer.objects.for_tenant(tenant).count()
    active_memberships = Membership.objects.for_tenant(tenant).filter(status=Membership.Status.ACTIVE).count()

    # MRR: active memberships normalized to a 30-day equivalent.
    mrr_total = Decimal(0)
    active_qs = Membership.objects.for_tenant(tenant).filter(status=Membership.Status.ACTIVE).select_related("plan")
    for membership in active_qs:
        plan = membership.plan
        if plan is not None and plan.duration_days:
            mrr_total += Decimal(str(plan.price or 0)) * Decimal(30) / Decimal(plan.duration_days)

    # Revenue summary (completed payments only).
    paid_qs = Payment.objects.for_tenant(tenant).filter(status=Payment.Status.COMPLETED)
    total_revenue = _sum(paid_qs.values_list("amount", flat=True))
    month_start = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
    this_month = _sum(paid_qs.filter(paid_at__gte=month_start).values_list("amount", flat=True))

    today_attendance = AttendanceRecord.objects.for_tenant(tenant).filter(date=today).count()

    trainer_count = User.objects.filter(tenant=tenant, role=User.Role.TRAINER, trainer_profile__isnull=False).count()

    pending_payments = Payment.objects.for_tenant(tenant).filter(status=Payment.Status.PENDING).count()

    data = {
        "total_members": total_members,
        "active_memberships": active_memberships,
        "mrr": str(round(float(mrr_total), 2)),
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


def get_revenue_breakdown(tenant: Any, period: str | None = None) -> dict:
    """Return revenue time-series for the frontend contract.

    Returns ``{"daily": [...], "weekly": [...], "monthly": [...]}`` where each
    series is a list of ``{"label": <str>, "amount": <float>}`` buckets:

    - ``daily``: the last 14 days (including today), labelled ``Sep 05``
    - ``weekly``: the last 12 Monday-start weeks, labelled by week start
    - ``monthly``: the last 12 calendar months, labelled ``Sep 2026``

    All buckets are present and zero-filled so charts render a continuous
    axis. ``period`` is accepted for backwards compatibility and ignored —
    all three series are always returned in a single payload.
    """
    del period  # Kept for backwards compatibility; all series are returned.

    today = timezone.localdate()
    daily_days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    current_week_start = today - timedelta(days=today.weekday())
    weekly_starts = [current_week_start - timedelta(weeks=i) for i in range(11, -1, -1)]

    month_starts: list[dt.date] = []
    cursor = today.replace(day=1)
    for _ in range(12):
        month_starts.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    month_starts.reverse()

    daily_totals = {day: Decimal(0) for day in daily_days}
    weekly_totals = {start: Decimal(0) for start in weekly_starts}
    monthly_totals = {start: Decimal(0) for start in month_starts}

    earliest = timezone.make_aware(datetime.combine(month_starts[0], datetime.min.time()))
    paid = Payment.objects.for_tenant(tenant).filter(
        status=Payment.Status.COMPLETED, paid_at__isnull=False, paid_at__gte=earliest
    )

    for payment in paid.iterator(chunk_size=500):
        day = timezone.localtime(payment.paid_at).date()
        amount = Decimal(payment.amount or 0)
        if day in daily_totals:
            daily_totals[day] += amount
        week_start = day - timedelta(days=day.weekday())
        if week_start in weekly_totals:
            weekly_totals[week_start] += amount
        month_key = day.replace(day=1)
        if month_key in monthly_totals:
            monthly_totals[month_key] += amount

    return {
        "daily": [{"label": day.strftime("%b %d"), "amount": round(float(daily_totals[day]), 2)} for day in daily_days],
        "weekly": [
            {"label": start.strftime("%b %d"), "amount": round(float(weekly_totals[start]), 2)}
            for start in weekly_starts
        ],
        "monthly": [
            {"label": start.strftime("%b %Y"), "amount": round(float(monthly_totals[start]), 2)}
            for start in month_starts
        ],
    }


def get_attendance_analytics(tenant: Any) -> dict:
    """Return attendance analytics for the frontend contract.

    ``peak_hours`` buckets check-ins by local hour with human labels
    (``"6 AM"``), and ``weekly_trend`` holds check-in counts for the last
    7 days labelled by weekday (``"Mon"``). Both use the
    ``{"hour": <label>, "check_ins": <count>}`` point shape the chart
    component expects.
    """
    qs = AttendanceRecord.objects.for_tenant(tenant)

    peak_qs = qs.annotate(hour=ExtractHour("check_in_time")).values("hour").annotate(count=Count("id")).order_by("hour")
    peak_hours = [{"hour": _hour_label(int(row["hour"] or 0)), "check_ins": row["count"]} for row in peak_qs]

    today = timezone.localdate()
    day_counts = {today - timedelta(days=offset): 0 for offset in range(6, -1, -1)}
    for check_in in qs.values_list("check_in_time", flat=True).iterator(chunk_size=500):
        day = timezone.localtime(check_in).date()
        if day in day_counts:
            day_counts[day] += 1

    weekly_trend = [{"hour": day.strftime("%a"), "check_ins": day_counts[day]} for day in day_counts]

    return {
        "peak_hours": peak_hours,
        "weekly_trend": weekly_trend,
    }


def _hour_label(hour: int) -> str:
    """Format a 0-23 hour as a human label (e.g. ``"6 AM"``, ``"12 PM"``)."""
    suffix = "AM" if hour < 12 else "PM"
    display = hour % 12 or 12
    return f"{display} {suffix}"


def get_membership_stats(tenant: Any) -> dict:
    """Return membership status breakdown and per-plan distribution."""
    qs = Membership.objects.for_tenant(tenant)

    breakdown = {
        "active": qs.filter(status=Membership.Status.ACTIVE).count(),
        "expired": qs.filter(status=Membership.Status.EXPIRED).count(),
        "cancelled": qs.filter(status=Membership.Status.CANCELLED).count(),
    }

    plan_rows = list(qs.values("plan__name").annotate(count=Count("id")).order_by("-count"))
    plan_distribution = [{"plan": row["plan__name"], "count": row["count"]} for row in plan_rows]

    return {
        "breakdown": breakdown,
        "plan_distribution": plan_distribution,
    }


def get_trainer_performance(tenant: Any) -> list[dict]:
    """Return top trainers ranked by revenue and client count.

    Combines per-month ``TrainerPerformance`` snapshots with live
    ``TrainerAssignment`` counts. Shape matches ``TrainerOverviewData``:
    ``{"id", "name", "revenue", "rating", "active_clients"}``.
    """
    perf = TrainerPerformance.objects.for_tenant(tenant)
    assignments = TrainerAssignment.objects.for_tenant(tenant).filter(is_active=True)

    revenue_by_trainer: dict[int, Decimal] = {}
    rating_by_trainer: dict[int, Decimal] = {}
    for row in perf.values("trainer_id", "revenue", "rating_avg", "sessions_completed"):
        tid = row["trainer_id"]
        revenue_by_trainer[tid] = revenue_by_trainer.get(tid, Decimal(0)) + row["revenue"]
        if row["rating_avg"] is not None:
            current = rating_by_trainer.get(tid)
            rating_by_trainer[tid] = max(current or Decimal(0), row["rating_avg"])

    client_count_by_trainer: dict[int, int] = {}
    for row in assignments.values("trainer_id").annotate(count=Count("id")):
        client_count_by_trainer[row["trainer_id"]] = row["count"]

    trainer_ids = set(revenue_by_trainer) | set(client_count_by_trainer)
    names = (
        {
            t.id: (t.user.get_full_name() or t.user.email)
            for t in User.objects.filter(id__in=trainer_ids, trainer_profile__isnull=False).select_related(
                "trainer_profile", "trainer_profile__user"
            )
        }
        if trainer_ids
        else {}
    )

    rows = []
    for tid in trainer_ids:
        rows.append(
            {
                "id": tid,
                "name": names.get(tid, f"Trainer #{tid}"),
                "revenue": round(float(revenue_by_trainer.get(tid, Decimal(0))), 2),
                "rating": (round(float(rating_by_trainer[tid]), 2) if tid in rating_by_trainer else 0.0),
                "active_clients": client_count_by_trainer.get(tid, 0),
            }
        )

    rows.sort(key=lambda r: (r["revenue"], r["active_clients"]), reverse=True)
    return rows


def get_pending_payments(tenant: Any) -> list[dict]:
    """Return pending payments with customer name, amount and due date.

    Due date is derived from the linked membership's end date when available,
    otherwise falls back to the payment's creation date.
    """
    pending = (
        Payment.objects.for_tenant(tenant)
        .filter(status=Payment.Status.PENDING)
        .select_related("customer", "membership")
        .order_by("-created_at")
    )
    rows = []
    for payment in pending:
        due_date = None
        if payment.membership and payment.membership.end_date:
            due_date = payment.membership.end_date.isoformat()
        elif payment.created_at:
            due_date = payment.created_at.date().isoformat()
        rows.append(
            {
                "id": payment.id,
                "customer_name": payment.customer.name,
                "amount": round(float(payment.amount), 2),
                "due_date": due_date,
            }
        )
    return rows


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
        cache = DashboardCache.objects.for_tenant(tenant).filter(metric_name=name).order_by("-date").first()
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
