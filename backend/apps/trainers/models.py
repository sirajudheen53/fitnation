"""Trainer management models (FBOS-007)."""

from django.db import models

from apps.tenants.models import TenantModelMixin


class TrainerAssignment(TenantModelMixin):
    """Branch-scoped trainer↔customer assignment.

    Complements ``users.TrainerCustomerAssignment`` (which is a direct, branch-agnostic
    mapping). This model adds a branch context so a trainer can serve a customer at a
    specific location. Both models may coexist for a given trainer/customer pair.

    Note: The customer FK uses ``related_name="trainer_assignment_records"`` because
    ``trainer_assignments`` is already claimed by ``users.TrainerCustomerAssignment``.
    """

    trainer = models.ForeignKey(
        "users.Trainer",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="trainer_assignment_records",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trainer_assignment_records",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """TrainerAssignment model metadata."""

        db_table = "trainer_assignments"
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "trainer", "customer"],
                name="uq_trainer_assignment_tenant_trainer_customer",
            ),
        ]

    def __str__(self) -> str:
        """Return assignment label."""
        return f"{self.trainer} → {self.customer} @ {self.branch or '—'}"


class TrainerPerformance(TenantModelMixin):
    """Monthly aggregate performance snapshot for a trainer."""

    trainer = models.ForeignKey(
        "users.Trainer",
        on_delete=models.CASCADE,
        related_name="performance_records",
    )
    month = models.DateField(
        help_text="First day of the month the snapshot applies to.",
    )
    revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Revenue attributed to the trainer in the month.",
    )
    customer_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of active customers served in the month.",
    )
    rating_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average trainer rating for the month (0.00–5.00).",
    )
    sessions_completed = models.PositiveIntegerField(
        default=0,
        help_text="Number of training sessions completed in the month.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """TrainerPerformance model metadata."""

        db_table = "trainer_performance"
        ordering = ["-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "trainer", "month"],
                name="uq_trainer_performance_tenant_trainer_month",
            ),
        ]

    def __str__(self) -> str:
        """Return performance label."""
        return f"{self.trainer} — {self.month}"
