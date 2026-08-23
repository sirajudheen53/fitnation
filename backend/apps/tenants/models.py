"""Tenant isolation foundation models."""

import uuid
from typing import Any

from django.db import models


class Tenant(models.Model):
    """Represents a vendor (gym business) on the platform. Root of all tenant-scoped data."""

    class SubscriptionPlan(models.TextChoices):
        """Available subscription tiers."""

        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        """Lifecycle states of a tenant."""

        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=300, blank=True)
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.STARTER,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
    )
    contact_email = models.EmailField(unique=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default="Asia/Kolkata")
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Tenant model metadata."""

        db_table = "tenants"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return human-readable tenant label."""
        return f"{self.name} ({self.subscription_plan})"


class TenantSettings(models.Model):
    """Per-tenant configuration: features, limits, branding."""

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="config",
    )
    max_branches = models.PositiveIntegerField(default=1)
    max_customers = models.PositiveIntegerField(default=100)
    max_trainers = models.PositiveIntegerField(default=5)
    logo_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#2563EB")
    enable_whatsapp = models.BooleanField(default=False)
    enable_razorpay = models.BooleanField(default=False)
    custom_domain = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """TenantSettings model metadata."""

        db_table = "tenant_settings"

    def __str__(self) -> str:
        """Return human-readable tenant settings label."""
        return f"Settings for {self.tenant.name}"


class TenantManager(models.Manager):
    """Manager that provides explicit tenant-scoped queries."""

    def for_tenant(self, tenant: "Tenant") -> models.QuerySet:
        """Return a queryset filtered to the supplied tenant.

        Args:
            tenant: The tenant instance to filter by.

        Returns:
            Queryset containing only rows belonging to the given tenant.
        """
        return self.get_queryset().filter(tenant=tenant)


class TenantModelMixin(models.Model):
    """Abstract base for all tenant-scoped models."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    objects = TenantManager()

    class Meta:
        """Mixin metadata."""

        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the model instance, enforcing a tenant is set.

        Raises:
            ValueError: If the instance has no tenant assigned.
        """
        if self.tenant_id is None:
            raise ValueError(f"{self.__class__.__name__} requires a tenant_id")
        super().save(*args, **kwargs)
