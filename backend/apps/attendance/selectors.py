"""Attendance read queries and statistics selectors."""

from collections import Counter
from datetime import timedelta

from django.utils import timezone

from apps.attendance.models import AttendanceRecord, StaffAttendance, TrainerAttendance


def attendance_stats(tenant) -> dict:
    """Compute attendance statistics for the tenant's check-ins (all person types).

    Returns the shape the frontend expects:
    ``{"stats": {...}, "summary": {"labels": [...], "check_ins": [...]}}``
    where the summary covers the last seven days of check-ins.
    """
    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    customer_records = AttendanceRecord.objects.for_tenant(tenant)
    trainer_records = TrainerAttendance.objects.for_tenant(tenant)
    staff_records = StaffAttendance.objects.for_tenant(tenant)

    def check_in_datetimes(queryset) -> list:
        """Return local check-in datetimes for a record queryset."""
        return [timezone.localtime(record.check_in_time) for record in queryset if record.check_in_time is not None]

    today_check_ins = (
        check_in_datetimes(customer_records.filter(date=today))
        + check_in_datetimes(trainer_records.filter(date=today))
        + check_in_datetimes(staff_records.filter(date=today))
    )
    week_check_ins = (
        check_in_datetimes(customer_records.filter(date__gte=week_start, date__lte=today))
        + check_in_datetimes(trainer_records.filter(date__gte=week_start, date__lte=today))
        + check_in_datetimes(staff_records.filter(date__gte=week_start, date__lte=today))
    )

    today_count = len(today_check_ins)
    weekly_check_ins = len(week_check_ins)
    avg_daily_check_ins = round(weekly_check_ins / 7, 1)

    hours = Counter(dt.hour for dt in today_check_ins)
    peak_hour: str | None = None
    peak_hour_count = 0
    if hours:
        busiest = max(hours, key=hours.get)
        peak_hour = f"{busiest:02d}:00"
        peak_hour_count = hours[busiest]

    labels: list[str] = []
    check_ins: list[int] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        labels.append(day.strftime("%a"))
        check_ins.append(sum(1 for dt in week_check_ins if dt.date() == day))

    checkout_records = (
        list(customer_records.filter(check_out_time__isnull=False, date__gte=week_start))
        + list(trainer_records.filter(check_out_time__isnull=False, date__gte=week_start))
        + list(staff_records.filter(check_out_time__isnull=False, date__gte=week_start))
    )
    dropout_hours = Counter(
        timezone.localtime(record.check_out_time).hour
        for record in checkout_records
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
