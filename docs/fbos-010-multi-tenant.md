# FBOS-010: Multi-Tenant Database Architecture

## Overview

Defines the tenant isolation strategy for FBOS — a multi-vendor SaaS platform where each gym vendor gets an isolated workspace. All tenant-scoped data is filtered via `tenant_id` at the Django ORM layer.

**Tenancy Model:** Row-level multi-tenancy (shared database, shared schema, tenant_id discriminator)
**Isolation Guarantee:** Enforced at the Django manager/queryset layer — no tenant-scoped model can be queried without a tenant filter.

---

## 1. Tenant Model

### Django Model

```python
# tenants/models.py

import uuid
from django.db import models


class Tenant(models.Model):
    """Represents a vendor (gym business) on the platform. Root of all tenant-scoped data."""

    class SubscriptionPlan(models.TextChoices):
        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=300, blank=True)
    subscription_plan = models.CharField(
        max_length=20, choices=SubscriptionPlan.choices, default=SubscriptionPlan.STARTER
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    contact_email = models.EmailField(unique=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default="Asia/Kolkata")
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.subscription_plan})"


class TenantSettings(models.Model):
    """Per-tenant configuration: features, limits, branding."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="config")
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
        db_table = "tenant_settings"
```

### SQL Migration

```sql
CREATE TABLE tenants (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(300) DEFAULT '',
    subscription_plan VARCHAR(20) NOT NULL DEFAULT 'starter',
    status VARCHAR(20) NOT NULL DEFAULT 'trial',
    contact_email VARCHAR(254) NOT NULL UNIQUE,
    contact_phone VARCHAR(20) DEFAULT '',
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tenant_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    max_branches INTEGER NOT NULL DEFAULT 1,
    max_customers INTEGER NOT NULL DEFAULT 100,
    max_trainers INTEGER NOT NULL DEFAULT 5,
    logo_url TEXT DEFAULT '',
    primary_color VARCHAR(7) DEFAULT '#2563EB',
    enable_whatsapp BOOLEAN DEFAULT FALSE,
    enable_azorpay BOOLEAN DEFAULT FALSE,
    custom_domain VARCHAR(255) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id)
);

CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_subscription_plan ON tenants(subscription_plan);
```

---

## 2. Tenant-Aware Base Model & Manager

### Abstract Base Model

Every tenant-scoped model inherits from `TenantModelMixin`. This guarantees a `tenant_id` FK and enforces filtering via the custom manager.

```python
# tenants/models.py (continued)

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
```

### Usage Example

```python
# branches/models.py

from tenants.models import TenantModelMixin


class Branch(TenantModelMixin):
    name = models.CharField(max_length=200)
    address = models.TextField()
    # tenant FK is inherited from TenantModelMixin

# Querying — always filter by tenant:
branches = Branch.objects.for_tenant(request.tenant).filter(is_active=True)

# NEVER do this in a view:
# branches = Branch.objects.all()  # <-- this bypasses tenant filter
```

---

## 3. Tenant Middleware

Extracts the tenant from the auth token and attaches it to `request.tenant`.

```python
# tenants/middleware.py

from django.core.exceptions import PermissionDenied
from tenants.models import Tenant


class TenantMiddleware:
    """
    Resolves the current tenant from the authenticated user's tenant_id.
    Platform admins (superusers) can optionally pass ?tenant_id= to impersonate.

    Sets: request.tenant = Tenant instance (or None for platform admin without impersonation)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        if hasattr(request, "user") and request.user.is_authenticated:
            if request.user.is_superuser:
                # Platform admin — can optionally impersonate a tenant
                tenant_id = request.GET.get("tenant_id")
                if tenant_id:
                    try:
                        request.tenant = Tenant.objects.get(id=tenant_id)
                    except Tenant.DoesNotExist:
                        raise PermissionDenied("Invalid tenant_id")
            elif request.user.tenant_id:
                request.tenant = request.user.tenant

        response = self.get_response(request)
        return response
```

### Middleware Order

```python
# settings.py — MIDDLEWARE ordering

MIDDLEWARE = [
    # ... standard Django middleware ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "tenants.middleware.TenantMiddleware",      # <-- right after AuthenticationMiddleware
    # ... rest ...
]
```

---

## 4. Tenant-Aware DRF Permission

```python
# tenants/permissions.py

from rest_framework.permissions import BasePermission


class IsTenantMember(BasePermission):
    """
    Allows access only if the user belongs to the request's tenant.
    Platform admins bypass this check.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.tenant is not None and request.user.tenant_id == request.tenant.id


class TenantReadOnly(BasePermission):
    """Read-only access within tenant."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated or request.tenant is None:
            return False
        return request.method in permissions.SAFE_METHODS
```

---

## 5. Database Indexes & Constraints

Every tenant-scoped table MUST have:

```sql
-- Composite index on (tenant_id, <common_filter_column>)
-- This is critical for query performance at scale.
CREATE INDEX idx_<table>_tenant_id ON <table>(tenant_id);
CREATE INDEX idx_<table>_tenant_created ON <table>(tenant_id, created_at DESC);

-- Unique constraints must include tenant_id to prevent cross-tenant collisions
-- Example: branch name unique within a tenant
ALTER TABLE branches ADD CONSTRAINT uq_branch_tenant_name
    UNIQUE(tenant_id, name);

-- Example: user email unique within a tenant
ALTER TABLE users ADD CONSTRAINT uq_user_tenant_email
    UNIQUE(tenant_id, email);
```

---

## 6. Data Migration & Backup Strategy

### Per-Tenant Backup

```python
# management/commands/backup_tenant.py

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("tenant_id", type=int)

    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        # Dump all rows where tenant_id = <tenant_id> across all tenant-scoped tables
        # Output to /backups/tenant_<tenant_id>_<timestamp>.sql
        tables = ["branches", "users", "customers", "memberships", "payments", ...]
        for table in tables:
            self.stdout.write(f"Dumping {table}...")
            # pg_dump with --where "tenant_id={tenant_id}"
```

### Tenant Provisioning (on vendor signup)

```python
# tenants/services.py

from tenants.models import Tenant, TenantSettings


def provision_tenant(name, contact_email, subscription_plan="starter", **kwargs):
    """
    Creates a new tenant and its settings. Called during vendor onboarding (FBOS-001).
    Returns the Tenant instance.
    """
    tenant = Tenant.objects.create(
        name=name,
        contact_email=contact_email,
        subscription_plan=subscription_plan,
        status=Tenant.Status.TRIAL,
        **kwargs,
    )
    TenantSettings.objects.create(tenant=tenant)

    # Set plan-based limits
    plan_limits = {
        "starter": {"max_branches": 1, "max_customers": 100, "max_trainers": 5},
        "professional": {"max_branches": 5, "max_customers": 1000, "max_trainers": 50},
        "enterprise": {"max_branches": 50, "max_customers": 10000, "max_trainers": 500},
    }
    limits = plan_limits.get(subscription_plan, plan_limits["starter"])
    tenant.config.max_branches = limits["max_branches"]
    tenant.config.max_customers = limits["max_customers"]
    tenant.config.max_trainers = limits["max_trainers"]
    tenant.config.save()

    return tenant
```

---

## 7. Connection Pooling

Use `django-db-geventpool` or `PgBouncer` for connection pooling. Tenant filtering is at the ORM layer (not connection-level), so standard pooling works.

**PgBouncer config** (recommended for production):

```ini
[databases]
fitnation = host=localhost port=5432 dbname=fitnation

[pgbouncer]
pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
```

---

## 8. Testing Strategy

```python
# tenants/tests.py

from django.test import TestCase
from tenants.models import Tenant
from branches.models import Branch


class TenantIsolationTest(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Gym A", contact_email="a@gym.com")
        self.tenant_b = Tenant.objects.create(name="Gym B", contact_email="b@gym.com")
        Branch.objects.create(tenant=self.tenant_a, name="Branch A1")
        Branch.objects.create(tenant=self.tenant_b, name="Branch B1")

    def test_tenant_a_cannot_see_tenant_b_branches(self):
        branches_a = Branch.objects.for_tenant(self.tenant_a)
        self.assertEqual(branches_a.count(), 1)
        self.assertEqual(branches_a.first().name, "Branch A1")

    def test_tenant_b_cannot_see_tenant_a_branches(self):
        branches_b = Branch.objects.for_tenant(self.tenant_b)
        self.assertEqual(branches_b.count(), 1)
        self.assertEqual(branches_b.first().name, "Branch B1")

    def test_save_without_tenant_raises(self):
        with self.assertRaises(ValueError):
            Branch.objects.create(name="Orphan Branch")  # No tenant

    def test_unique_within_tenant(self):
        Branch.objects.create(tenant=self.tenant_a, name="Branch A1")
        with self.assertRaises(Exception):
            Branch.objects.create(tenant=self.tenant_a, name="Branch A1")
        # Same name in different tenant is fine
        Branch.objects.create(tenant=self.tenant_b, name="Branch A1")
```

---

## 9. Implementation Checklist

| # | Task | Owner | Status |
|---|------|-------|--------|
| 1 | Create `tenants` Django app | Backend | ☐ |
| 2 | Implement `Tenant`, `TenantSettings` models | Backend | ☐ |
| 3 | Implement `TenantModelMixin`, `TenantManager` | Backend | ☐ |
| 4 | Implement `TenantMiddleware` | Backend | ☐ |
| 5 | Add middleware to `settings.py` | Backend | ☐ |
| 6 | Implement `IsTenantMember` permission | Backend | ☐ |
| 7 | Implement `provision_tenant()` service | Backend | ☐ |
| 8 | Write tenant isolation tests | Backend | ☐ |
| 9 | Apply migrations + run tests | Backend | ☐ |
| 10 | Configure PgBouncer (staging) | DevOps | ☐ |

---

## 10. Cross-Story Dependencies

- **FBOS-001 (Vendor Onboarding):** Calls `provision_tenant()` to create the tenant record. The vendor signup flow creates a Tenant + TenantSettings + owner User.
- **FBOS-002 (Branch Management):** Branch model inherits `TenantModelMixin`. All branch queries use `for_tenant()`.
- **FBOS-009 (Roles & Permissions):** User model has `tenant_id` FK. Role checks are scoped within tenant context.
- **All future stories:** Every tenant-scoped model MUST inherit `TenantModelMixin`. No exceptions.