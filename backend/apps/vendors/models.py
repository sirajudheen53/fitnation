"""Vendor onboarding and subscription plan models."""

import uuid

from django.db import models


class VendorRegistration(models.Model):
    """Tracks the vendor registration state machine until onboarding is complete."""

    class Step(models.TextChoices):
        """Registration lifecycle steps."""

        STARTED = "started", "Started"
        EMAIL_VERIFIED = "email_verified", "Email Verified"
        PLAN_SELECTED = "plan_selected", "Plan Selected"
        PROVISIONED = "provisioned", "Provisioned"
        ONBOARDED = "onboarded", "Onboarded"

    email = models.EmailField(unique=True)
    business_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    contact_phone = models.CharField(max_length=20, blank=True)
    password_hash = models.CharField(max_length=128)
    selected_plan = models.CharField(
        max_length=20,
        choices=[
            ("starter", "Starter"),
            ("professional", "Professional"),
            ("enterprise", "Enterprise"),
        ],
        blank=True,
    )
    email_verification_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    current_step = models.CharField(
        max_length=20,
        choices=Step.choices,
        default=Step.STARTED,
    )
    provisioned_tenant_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """VendorRegistration model metadata."""

        db_table = "vendor_registrations"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return registration label."""
        return f"{self.business_name} ({self.email}) — {self.current_step}"


class SubscriptionPlan(models.Model):
    """Defines available subscription tiers and their features."""

    class PlanCode(models.TextChoices):
        """Plan codes."""

        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    code = models.CharField(max_length=20, choices=PlanCode.choices, unique=True)
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_branches = models.PositiveIntegerField()
    max_customers = models.PositiveIntegerField()
    max_trainers = models.PositiveIntegerField()
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """SubscriptionPlan model metadata."""

        db_table = "subscription_plans"
        ordering = ["sort_order"]

    def __str__(self) -> str:
        """Return plan label."""
        return f"{self.name} — ₹{self.price_monthly}/mo"
