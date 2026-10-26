"""Trainer management models (FBOS-007, issue #52)."""

from typing import ClassVar

from django.db import models

from apps.tenants.models import TenantModelMixin

MAX_SESSION_DURATION_MINUTES = 480


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
        # Issue #81: assignment history survives a deleted customer.
        on_delete=models.PROTECT,
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
        ordering: ClassVar[list[str]] = ["-assigned_at"]
        constraints: ClassVar[list] = [
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
        ordering: ClassVar[list[str]] = ["-month"]
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["tenant", "trainer", "month"],
                name="uq_trainer_performance_tenant_trainer_month",
            ),
        ]

    def __str__(self) -> str:
        """Return performance label."""
        return f"{self.trainer} — {self.month}"


class TrainerSession(TenantModelMixin):
    """A scheduled personal-training session between a trainer and a customer.

    Session lifecycle (issue #52): a session is created ``booked`` and moves to
    ``completed``, ``no_show`` or ``cancelled``. Completed and no-show sessions
    redeem one session from the customer's active PT membership pack (derived
    count, never stored — cancelling such a session restores the credit).
    """

    class Status(models.TextChoices):
        """Lifecycle status of a training session."""

        BOOKED = "booked", "Booked"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No-show"

    #: Statuses that redeem one session from the customer's PT pack.
    REDEEM_STATUSES: ClassVar[tuple[str, ...]] = (Status.COMPLETED, Status.NO_SHOW)

    trainer = models.ForeignKey(
        "users.Trainer",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        # Issue #81: PT-session history survives a deleted customer.
        on_delete=models.PROTECT,
        related_name="trainer_sessions",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trainer_sessions",
    )
    scheduled_at = models.DateTimeField(help_text="Session start (timezone-aware).")
    duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Slot length in minutes; the session occupies [scheduled_at, scheduled_at + duration).",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BOOKED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """TrainerSession model metadata."""

        db_table = "trainer_sessions"
        ordering: ClassVar[list[str]] = ["-scheduled_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["tenant", "trainer", "scheduled_at"], name="idx_sess_tenant_trainer_sched"),
            models.Index(fields=["tenant", "customer", "status"], name="idx_sess_tenant_cust_status"),
        ]
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gte=1)
                & models.Q(duration_minutes__lte=MAX_SESSION_DURATION_MINUTES),
                name="ck_trainer_session_duration_range",
            ),
        ]

    def __str__(self) -> str:
        """Return session label."""
        return f"{self.trainer} × {self.customer} @ {self.scheduled_at:%Y-%m-%d %H:%M} ({self.status})"

    @property
    def ends_at(self):
        """Return the slot end (scheduled_at + duration)."""
        from datetime import timedelta

        return self.scheduled_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_redeemed(self) -> bool:
        """Whether this session currently redeems a pack credit."""
        return self.status in self.REDEEM_STATUSES
