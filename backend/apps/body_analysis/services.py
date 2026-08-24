"""Business logic for body analysis."""

from datetime import date
from typing import Any

from django.db.models import DecimalField
from django.db.models.functions import Cast

from apps.body_analysis.models import BodyAnalysis, BodyPhoto, BodyProgressLog


def create_photo_for_analysis(
    *,
    tenant: Any,
    analysis_id: int,
    photo_type: str,
    image_url: str,
) -> BodyPhoto:
    """Attach a new photo to a body analysis and bump its photo count.

    Args:
        tenant: The request tenant.
        analysis_id: PK of the target ``BodyAnalysis``.
        photo_type: One of ``front``/``side``/``back``.
        image_url: Stored URL of the uploaded photo.

    Returns:
        The created ``BodyPhoto`` instance.

    Raises:
        BodyAnalysis.DoesNotExist: If the analysis is missing or not in the tenant.
    """
    analysis = BodyAnalysis.objects.for_tenant(tenant).get(id=analysis_id)
    photo = BodyPhoto.objects.create(
        tenant=tenant,
        analysis=analysis,
        photo_type=photo_type,
        image_url=image_url,
    )
    analysis.photo_count = analysis.photos.count()
    analysis.save(update_fields=["photo_count"])
    return photo


def build_progress_trend(
    *,
    tenant: Any,
    user_id: int,
    metric_type: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Return chronological (date, value) points for a metric.

    Args:
        tenant: The request tenant.
        user_id: The user whose logs should be aggregated.
        metric_type: One of ``BodyProgressLog.MetricType`` values.
        start_date: Optional inclusive lower date bound.
        end_date: Optional inclusive upper date bound.

    Returns:
        A list of ``{"date": ..., "value": ...}`` ordered by date ascending.
    """
    qs = (
        BodyProgressLog.objects.for_tenant(tenant)
        .filter(user_id=user_id, metric_type=metric_type)
        .annotate(value_num=Cast("value", DecimalField()))
    )
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)

    # Latest value wins if multiple logs share a date (process oldest first,
    # newest last so the overwrite keeps the most recent reading).
    by_date: dict[date, float] = {}
    for log in qs.order_by("date", "created_at", "id"):
        by_date[log.date] = float(log.value)

    return [
        {"date": d.isoformat(), "value": v}
        for d, v in sorted(by_date.items())
    ]
