"""Attendance read queries and statistics selectors."""

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import ExtractHour
from django.utils import timezone

from apps.attendance.models import AttendanceRecord, StaffAttendance, TrainerAttendance


def _hour_histogram(queryset, field: str) -> dict[int, int]:
    """Group a queryset's local hour counts in SQL.

    Returns ``{hour: count}`` for non-null values of ``field``. The previous
    Python implementation hydrated every row and Counter-picked the busiest
    hour; grouping in SQL keeps the counts identical without loading rows
    (#82). Ties resolve to the newest (largest) hour, matching the old
    newest-first scan order.
    """
    rows = (
        queryset.filter(**{f"{field}__isnull": False})
        .annotate(bucket=ExtractHour(field))
        .values("bucket")
        .annotate(count=Count("id"))
        .order_by("-count", "-bucket")
    )
    return {row["bucket"]: row["count"] for row in rows}


def _merge_histograms(histograms: list[dict[int, int]]) -> dict[int, int]:
    """Sum per-hour counts across the person-type tables (old Counter behavior)."""
    merged: dict[int, int] = {}
    for histogram in histograms:
        for hour, count in histogram.items():
            merged[hour] = merged.get(hour, 0) + count
    return merged


def _busiest_hour(histogram: dict[int, int]) -> tuple[int, int] | None:
    """Return the (hour, count) with the most check-ins, or None when empty."""
    if not histogram:
        return None
    hour = max(histogram, key=lambda h: (histogram[h], h))
    return hour, histogram[hour]


def attendance_stats(tenant) -> dict:
    """Compute attendance statistics for the tenant's check-ins (all person types).

    Returns the shape the frontend expects:
    ``{"stats": {...}, "summary": {"labels": [...], "check_ins": [...]}}``
    where the summary covers the last seven days of check-ins.

    Every metric is aggregated in SQL (#82) — a handful of small grouped
    queries (three per person type) instead of loading a week of attendance
    rows into Python.
    """
    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    sources = [
        AttendanceRecord.objects.for_tenant(tenant),
        TrainerAttendance.objects.for_tenant(tenant),
        StaffAttendance.objects.for_tenant(tenant),
    ]

    today_hours: list[dict[int, int]] = []
    dropout_hours: list[dict[int, int]] = []
    day_counts: dict = {}

    for records in sources:
        # Today's check-ins: the hour histogram doubles as the today count
        # (peak hour is computed over today only, as before).
        today_hours.append(_hour_histogram(records.filter(date=today), "check_in_time"))

        # Week: per-day counts over the indexed date column, which every
        # writer keeps equal to the local date of check_in_time.
        week_rows = records.filter(date__gte=week_start, date__lte=today).values("date").annotate(count=Count("id"))
        for row in week_rows:
            day_counts[row["date"]] = day_counts.get(row["date"], 0) + row["count"]

        # Dropouts: check-out hour histogram since the week started.
        dropout_hours.append(
            _hour_histogram(
                records.filter(check_out_time__isnull=False, date__gte=week_start),
                "check_out_time",
            )
        )

    today_count = sum(sum(h.values()) for h in today_hours)
    weekly_check_ins = sum(day_counts.values())
    avg_daily_check_ins = round(weekly_check_ins / 7, 1)

    peak = _busiest_hour(_merge_histograms(today_hours))
    dropout = _busiest_hour(_merge_histograms(dropout_hours))
    peak_hour = f"{peak[0]:02d}:00" if peak is not None else None
    peak_hour_count = peak[1] if peak is not None else 0
    most_frequent_dropout_hour = f"{dropout[0]:02d}:00" if dropout is not None else None

    labels: list[str] = []
    check_ins: list[int] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        labels.append(day.strftime("%a"))
        check_ins.append(day_counts.get(day, 0))

    return {
        "stats": {
            "today_count": today_count,
            "peak_hour": peak_hour,
            "peak_hour_count": peak_hour_count,
            "weekly_check_ins": weekly_check_ins,
            "avg_daily_check_ins": avg_daily_check_ins,
            "most_frequent_dropout_hour": most_frequent_dropout_hour,
        },
        "summary": {"labels": labels, "check_ins": check_ins},
    }
