"""Dashboard aggregation models (FBOS-008)."""

from typing import ClassVar

from django.db import models

from apps.tenants.models import TenantModelMixin


class DashboardCache(TenantModelMixin):
    """Cached dashboard metric snapshots per tenant.

    Heavy aggregation queries can be wrapped with ``DashboardCache`` reads/writes
    so repeated dashboard views avoid recomputing expensive series. A unique
    constraint on ``(tenant, metric_name, date)`` ensures at most one snapshot per
    metric per day.
    """

    metric_name = models.CharField(max_length=100)
    metric_value = models.JSONField(default=dict, blank=True)
    date = models.DateField(auto_now_add=True)
    auto_updated = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """DashboardCache model metadata."""

        db_table = "dashboard_cache"
        ordering: ClassVar[list] = ["-date"]
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["tenant", "metric_name", "date"],
                name="uq_dashboard_cache_tenant_metric_date",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable cache label."""
        return f"{self.metric_name} @ {self.date}"
