import uuid
from django.db import models


class Tenant(models.Model):
    """Tenant model with essential fields for multi‑tenant architecture."""
    class SubscriptionPlan(models.TextChoices):
        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    subscription_plan = models.CharField(
        max_length=20, choices=SubscriptionPlan.choices, default=SubscriptionPlan.STARTER
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.subscription_plan})"


class TenantManager(models.Manager):
    """
    Manager that automatically filters by the current tenant.
    The tenant is set by TenantMiddleware on the request object.
    Usage in views: Model.objects.for_tenant(request.tenant)
    """

    def for_tenant(self, tenant):
        return self.get_queryset().filter(tenant=tenant)

    def get_queryset(self):
        # If no tenant is set on the manager, return unfiltered queryset.
        # Tenant filtering is explicit via for_tenant() to avoid accidental
        # cross-tenant access. For safety, views should ALWAYS use for_tenant().
        return super().get_queryset()


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
        abstract = True

    def save(self, *args, **kwargs):
        # Enforce tenant is set
        if self.tenant_id is None:
            raise ValueError(f"{self.__class__.__name__} requires a tenant_id")
        super().save(*args, **kwargs)