"""Analytics models (computed views).

We store aggregated data to enable efficient reporting. Each model is tenant-scoped
via ``TenantModelMixin`` and includes the minimal fields required for the
corresponding endpoint.
"""

from django.db import models

from apps.tenants.models import TenantModelMixin


class RevenueReport(TenantModelMixin):
    """Aggregated revenue for a given period.

    * ``period`` – date representing the start of the period (day, week, month).
    * ``amount`` – total revenue (in the smallest currency unit, e.g., paise).
    """

    period = models.DateField(db_index=True)
    amount = models.BigIntegerField()

    class Meta:
        """RevenueReport model metadata."""

        db_table = "analytics_revenue_report"
        ordering = ["-period"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period"],
                name="uq_analytics_revenue_tenant_period",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable revenue report label."""
        return f"Revenue {self.period} — {self.amount}"


class AttendanceHeatmap(TenantModelMixin):
    """Aggregated attendance counts per day for heat-map visualisation.

    * ``date`` – the day.
    * ``count`` – number of attendance records.
    """

    date = models.DateField(db_index=True)
    count = models.PositiveIntegerField()

    class Meta:
        """AttendanceHeatmap model metadata."""

        db_table = "analytics_attendance_heatmap"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "date"],
                name="uq_analytics_heatmap_tenant_date",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable heatmap label."""
        return f"Attendance {self.date} — {self.count}"


class MembershipFunnel(TenantModelMixin):
    """Counts of customers at each stage of the membership funnel.

    * ``stage`` – one of ``prospect``, ``trial``, ``active``, ``cancelled``.
    * ``count`` – number of customers in that stage.
    """

    class Stage(models.TextChoices):
        """Membership funnel stages."""

        PROSPECT = "prospect", "Prospect"
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"

    stage = models.CharField(max_length=20, choices=Stage.choices)
    count = models.PositiveIntegerField()

    class Meta:
        """MembershipFunnel model metadata."""

        db_table = "analytics_membership_funnel"
        ordering = ["stage"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "stage"],
                name="uq_analytics_funnel_tenant_stage",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable funnel label."""
        return f"{self.stage} — {self.count}"


class TopCustomer(TenantModelMixin):
    """A customer ranked by total spend.

    * ``customer_id`` – FK to ``customers.Customer`` (stored as integer to avoid
      circular import).
    * ``total_spent`` – total amount spent.
    """

    customer_id = models.BigIntegerField(db_index=True)
    total_spent = models.BigIntegerField()

    class Meta:
        """TopCustomer model metadata."""

        db_table = "analytics_top_customer"
        ordering = ["-total_spent"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "customer_id"],
                name="uq_analytics_topcustomer_tenant_customer",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable top-customer label."""
        return f"Customer #{self.customer_id} — {self.total_spent}"
