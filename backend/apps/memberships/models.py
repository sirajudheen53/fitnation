"""Membership management models."""

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin


class MembershipPlan(TenantModelMixin):
    """A sellable membership plan offered by a tenant (gym)."""

    class PlanType(models.TextChoices):
        """Supported membership plan types."""

        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        PT = "pt", "Personal Training"
        TRIAL = "trial", "Trial"

    name = models.CharField(max_length=200)
    plan_type = models.CharField(
        max_length=20,
        choices=PlanType.choices,
        default=PlanType.MONTHLY,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """MembershipPlan model metadata."""

        db_table = "membership_plans"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_membership_plan_tenant_name",
            ),
        ]

    def __str__(self) -> str:
        """Return plan label."""
        return f"{self.name} ({self.plan_type})"


class Membership(TenantModelMixin):
    """A customer's membership subscription for a plan."""

    class Status(models.TextChoices):
        """Lifecycle status of a membership."""

        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Membership model metadata."""

        db_table = "memberships"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "customer"], name="idx_membership_tenant_customer"),
        ]

    def __str__(self) -> str:
        """Return membership label."""
        return f"{self.customer} — {self.plan.name}"

    def compute_status(self) -> str:
        """Compute the effective status based on end_date.

        A membership is active while today <= end_date and not cancelled.
        Once the end_date passes, it transitions to expired (unless cancelled).

        Returns:
            The computed status string.
        """
        if self.status == self.Status.CANCELLED:
            return self.Status.CANCELLED
        if self.end_date is not None and timezone.localdate() > self.end_date:
            return self.Status.EXPIRED
        return self.Status.ACTIVE

    def refresh_status(self) -> None:
        """Refresh the stored status from the computed status, without saving.

        Updates ``self.status`` in memory; call ``save()`` to persist.
        """
        self.status = self.compute_status()

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the membership, keeping status in sync with dates.

        Status is only auto-adjusted when not explicitly cancelled so that a
        cancelled membership remains cancelled.
        """
        self.refresh_status()
        super().save(*args, **kwargs)


class Coupon(TenantModelMixin):
    """A discount coupon redeemable against memberships."""

    code = models.CharField(max_length=50)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Coupon model metadata."""

        db_table = "coupons"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="uq_coupon_tenant_code",
            ),
        ]

    def __str__(self) -> str:
        """Return coupon label."""
        return f"{self.code} ({self.discount_percent}%)"
