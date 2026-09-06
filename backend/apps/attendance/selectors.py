"""Attendance read queries and statistics selectors."""

from collections import Counter
from datetime import timedelta

from django.utils import timezone

from apps.attendance.models import AttendanceRecord


def attendance_stats(tenant) -> dict:
    """Compute attendance statistics for the tenant's customer check-ins.

    Returns the shape the frontend expects:
    ``{"stats": {...}, "summary": {"labels": [...], "check_ins": [...]}}``
    where the summary covers the last seven days of check-ins.
    """
    today = timezone.localdate()
    week_start = today - timedelta(days=6)
    records = AttendanceRecord.objects.for_tenant(tenant)
    today_records = records.filter(date=today)
    weekly = records.filter(date__gte=week_start, date__lte=today)

    today_count = today_records.count()
    weekly_check_ins = weekly.count()
    avg_daily_check_ins = round(weekly_check_ins / 7, 1)

    labels: list[str] = []
    check_ins: list[int] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        labels.append(day.strftime("%a"))
        check_ins.append(records.filter(date=day).count())

    peak_hour: str | None = None
    peak_hour_count = 0
    hours = Counter(
        timezone.localtime(record.check_in_time).hour
        for record in today_records
        if record.check_in_time is not None
    )
    if hours:
        hour, count = max(hours.items(), key=lambda item: item[1])
        peak_hour = f"{hour:02d}:00"
        peak_hour_count = count

    dropout_hours = Counter(
        timezone.localtime(record.check_out_time).hour
        for record in weekly
        if record.check_out_time is not None
    )
    most_frequent_dropout_hour: str | None = None
    if dropout_hours:
        busiest = max(dropout_hours, key=dropout_hours.get)
        most_frequent_dropout_hour = f"{busiest:02d}:00"

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