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

from django.db.models import Count, DateField, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import ExtractHour, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.customers.models import Customer
from apps.dashboard.models import DashboardCache
from apps.memberships.models import Membership
from apps.payments.models import Payment
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.users.models import User

# Issue #84: marker stamped on cached overview payloads so same-day cache rows
# computed before lapsed memberships counted as pending dues are recomputed.
PENDING_DUES_SEMANTICS = "issue-84"


def get_overview(tenant: Any) -> dict:
    """Return the top-level dashboard overview for a tenant.

    Composes total members, active memberships, revenue summary, today's
    attendance, trainer count and pending payments.
    """
    cached = _read(tenant, "overview")
    # Reject cached payloads that predate the current contract: rows without
    # "mrr" lack the MRR field; rows without the issue-84 marker were computed
    # before lapsed memberships counted as pending dues, so a same-day cache
    # row would otherwise serve the old (zero-while-expired) count.
    if (
        cached is not None
        and isinstance(cached, dict)
        and "mrr" in cached
        and cached.get("pending_dues_semantics") == PENDING_DUES_SEMANTICS
    ):
        return cached

    today = timezone.localdate()

    total_members = Customer.objects.for_tenant(tenant).count()
    active_memberships = Membership.objects.for_tenant(tenant).filter(status=Membership.Status.ACTIVE).count()

    # MRR: active memberships normalized to a 30-day equivalent. One SQL
    # aggregation (SUM(price * 30 / duration_days)) instead of loading every
    # active membership + plan into Python (#82).
    mrr_total = (
        Membership.objects.for_tenant(tenant)
        .filter(status=Membership.Status.ACTIVE, plan__duration_days__gt=0)
        .aggregate(
            total=Sum(
                ExpressionWrapper(
                    # 30.0 (not 30): SQLite does integer division for
                    # int/int operands, truncating the 30-day normalization.
                    F("plan__price") * Value(30.0) / F("plan__duration_days"),
                    output_field=DecimalField(max_digits=21, decimal_places=6),
                )
            )
        )["total"]
    ) or Decimal(0)

    # Revenue summary (completed payments only).
    paid_qs = Payment.objects.for_tenant(tenant).filter(status=Payment.Status.COMPLETED)
    total_revenue = paid_qs.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    month_start = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
    this_month = paid_qs.filter(paid_at__gte=month_start).aggregate(total=Sum("amount"))["total"] or Decimal(0)

    today_attendance = AttendanceRecord.objects.for_tenant(tenant).filter(date=today).count()

    trainer_count = User.objects.filter(tenant=tenant, role=User.Role.TRAINER, trainer_profile__isnull=False).count()

    # Count without materializing the queue rows (#82): explicit pending
    # payments plus one due per customer, matching get_pending_payments().
    pending_payments = (
        Payment.objects.for_tenant(tenant).filter(status=Payment.Status.PENDING).count()
        + _dues_queryset(tenant).aggregate(count=Count("customer_id", distinct=True))["count"]
    )

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
        # Cache-shape marker (stripped by OverviewSerializer): see _read guard.
        "pending_dues_semantics": PENDING_DUES_SEMANTICS,
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

    earliest = timezone.make_aware(datetime.combine(month_starts[0], datetime.min.time()))
    paid = Payment.objects.for_tenant(tenant).filter(
        status=Payment.Status.COMPLETED, paid_at__isnull=False, paid_at__gte=earliest
    )

    daily_totals = _bucket_totals(paid, TruncDate("paid_at"), daily_days)
    # TruncWeek/TruncMonth truncate to datetimes by default — force a date
    # output so buckets match the Python date keys.
    weekly_totals = _bucket_totals(paid, TruncWeek("paid_at", output_field=DateField()), weekly_starts)
    monthly_totals = _bucket_totals(paid, TruncMonth("paid_at", output_field=DateField()), month_starts)

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

    # 7-day trend: grouped in SQL over the indexed date column, filtered to
    # the window — previously this pulled every check-in the tenant ever had
    # into Python (#82). ``date`` is always the local date of ``check_in_time``
    # (model save() and every writer derive it that way).
    today = timezone.localdate()
    day_counts = {today - timedelta(days=offset): 0 for offset in range(6, -1, -1)}
    trend_rows = qs.filter(date__gte=today - timedelta(days=6)).values("date").annotate(count=Count("id"))
    for row in trend_rows:
        if row["date"] in day_counts:
            day_counts[row["date"]] = row["count"]

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

    # One pass for the status counts (#82) instead of a query per status.
    counts = qs.aggregate(
        active=Count("id", filter=Q(status=Membership.Status.ACTIVE)),
        expired=Count("id", filter=Q(status=Membership.Status.EXPIRED)),
        cancelled=Count("id", filter=Q(status=Membership.Status.CANCELLED)),
    )
    breakdown = {
        "active": counts["active"],
        "expired": counts["expired"],
        "cancelled": counts["cancelled"],
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
    """Return the unified pending-payment queue for a tenant (issue #84).

    "Pending" is money the gym is owed right now, from two sources:

    1. Explicit pending ``Payment`` records (issue #72 send-link queue).
    2. Membership dues — a membership whose ``end_date`` has passed (not
       cancelled) with no covering charge. The amount is the plan price,
       matching the renewal contract: ``POST /memberships/{id}/renewal/``
       extends the SAME membership, so the expected renewal due for a lapsed
       member is exactly the plan's price.

    Guards keep the queue free of double counting:

    - active memberships (``end_date`` >= today) and cancelled ones are not
      dues — lapsedness is judged by ``end_date``, not the stored status,
      which can be stale until the next save;
    - a customer with an explicit pending membership-kind payment already has
      their charge tracked, so the derived due is suppressed for them (an
      admission-fee pending payment does NOT cover a renewal);
    - one due per customer: their most recently lapsed membership.

    Derived rows carry a negative id (``abs(id)`` = membership id) so they
    stay unique next to real payment ids while the row shape
    (id/customer_name/customer_is_deleted/amount/due_date) is unchanged for
    the frontend. Soft-deleted members keep their due (money is owed
    regardless); the frontend already renders the deleted-user marker.

    Order: explicit payments first, newest first, then dues, most-lapsed
    (oldest end_date) first.
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
                # Issue #81: the row's member was deleted (name shows the marker).
                "customer_is_deleted": payment.customer.deleted_at is not None,
                "amount": round(float(payment.amount), 2),
                "due_date": due_date,
            }
        )
    rows.extend(_membership_dues(tenant))
    return rows


def _membership_dues(tenant: Any) -> list[dict]:
    """Derived pending dues for lapsed memberships without a covering charge."""
    # One values() pass instead of instantiating every lapsed membership +
    # customer + plan (#82). First row per customer wins, i.e. the most
    # recently lapsed membership (query orders by -end_date, -id).
    rows = _dues_queryset(tenant).values(
        "id",
        "customer_id",
        "end_date",
        "plan__price",
        "customer__name",
        "customer__deleted_at",
    )
    latest_by_customer: dict[int, dict] = {}
    for row in rows:
        latest_by_customer.setdefault(row["customer_id"], row)

    dues = [
        {
            "id": -row["id"],
            "customer_name": row["customer__name"],
            "customer_is_deleted": bool(row["customer__deleted_at"]),
            "amount": round(float(row["plan__price"] or 0), 2),
            "due_date": row["end_date"].isoformat(),
        }
        for row in sorted(latest_by_customer.values(), key=lambda r: r["end_date"])
    ]
    return dues


def _dues_queryset(tenant: Any):
    """Lapsed, non-cancelled memberships with no covering pending charge.

    Shared by the dues list (:func:`_membership_dues`) and the overview's
    pending count so both always agree on what counts as a due (issue #84
    semantics). A customer with an explicit pending membership-kind payment
    has their charge tracked, so their memberships are excluded here.
    """
    covered_customers = (
        Payment.objects.for_tenant(tenant)
        .filter(status=Payment.Status.PENDING, kind=Payment.Kind.MEMBERSHIP)
        .values("customer_id")
    )
    return (
        Membership.objects.for_tenant(tenant)
        .filter(end_date__lt=timezone.localdate())
        .exclude(status=Membership.Status.CANCELLED)
        .exclude(customer_id__in=covered_customers)
    )


def _bucket_totals(paid: Any, truncation: Any, buckets: list[dt.date]) -> dict[dt.date, Decimal]:
    """Sum completed payments into date buckets in SQL (#82).

    Groups by the truncated ``paid_at`` (day / Monday-start week / calendar
    month — matching the previous Python-side bucketing) and returns a
    zero-filled ``{bucket: total}`` map. Buckets outside the truncated rows
    (future dates, older payments beyond the window) stay at Decimal zero.
    """
    totals = dict.fromkeys(buckets, Decimal(0))
    rows = paid.annotate(bucket=truncation).values("bucket").annotate(total=Sum("amount"))
    for row in rows:
        if row["bucket"] in totals:
            totals[row["bucket"]] += row["total"] or Decimal(0)
    return totals


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
