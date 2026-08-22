# FBOS-009: Roles & Permissions System

## Overview

Defines the role hierarchy, permission matrix, DRF permission classes, and token-based authentication with tenant context for FBOS.

**Depends on:** FBOS-010 (Tenant model), FBOS-001 (User model with `tenant_id` and `role`)
**Authentication:** Token-based (DRF TokenAuthentication) with tenant context injected by middleware.

---

## 1. Role Hierarchy

```
                    ┌─────────────────┐
                    │ PLATFORM_ADMIN   │  (superuser, tenant_id=NULL)
                    │  Siju / FBOS team │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  GYM_OWNER       │  (is_owner=True, created during onboarding)
                    │  Full tenant access│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐ ┌────▼────────┐ ┌───▼──────────┐
     │  MANAGER      │ │  TRAINER    │ │  DIETITIAN   │
     │  Branch-level │ │  Customers  │ │  Diet plans  │
     │  operations   │ │  Workouts   │ │              │
     └───────────────┘ └─────────────┘ └──────────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  CUSTOMER        │  (mobile app user)
                    │  Self-service     │
                    └─────────────────┘
```

### Role Definitions

| Role | Code | Tenant-scoped? | Description |
|------|------|----------------|-------------|
| Platform Admin | `platform_admin` | No (superuser) | Manages all tenants, subscriptions, platform settings |
| Gym Owner | `gym_owner` | Yes | Full access to their tenant data. Created during vendor onboarding. |
| Manager | `manager` | Yes | Branch-level operations: customers, memberships, payments, attendance |
| Trainer | `trainer` | Yes | Manages assigned customers, workout plans, attendance logging |
| Dietitian | `dietitian` | Yes | Manages assigned customers, diet plans, nutrition tracking |
| Customer | `customer` | Yes | Self-service: views own workouts, diet, payments, attendance |

---

## 2. Permission Matrix

### Permission Codes

Format: `{app}.{action}_{model}` (e.g., `branches.create_branch`, `customers.view_customer`)

### Matrix

| Resource | Platform Admin | Gym Owner | Manager | Trainer | Dietitian | Customer |
|----------|:-:|:-:|:-:|:-:|:-:|:-:|
| **Tenants** | | | | | | |
| View all tenants | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Update tenant settings | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Branches** | | | | | | |
| View branches | ✅ (all) | ✅ (own) | ✅ (own) | ✅ (assigned) | ❌ | ❌ |
| Create/edit/delete branches | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Users** | | | | | | |
| View users in tenant | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Create/edit users | ✅ | ✅ | ✅ (managers, trainers) | ❌ | ❌ | ❌ |
| Delete/deactivate users | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Customers** | | | | | | |
| View customers | ✅ (all) | ✅ | ✅ | ✅ (assigned) | ✅ (assigned) | ✅ (self only) |
| Create/edit customers | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete customers | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Trainers** | | | | | | |
| View trainers | ✅ | ✅ | ✅ | ✅ (self) | ❌ | ❌ |
| Create/edit trainers | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Memberships** | | | | | | |
| View memberships | ✅ | ✅ | ✅ | ✅ (assigned) | ❌ | ✅ (self) |
| Create/edit memberships | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Payments** | | | | | | |
| View payments | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ (self) |
| Record payments | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Attendance** | | | | | | |
| View attendance | ✅ | ✅ | ✅ | ✅ (assigned) | ❌ | ✅ (self) |
| Log attendance | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ (check-in) |
| **Workout Plans** | | | | | | |
| View workout plans | ✅ | ✅ | ✅ | ✅ (own) | ❌ | ✅ (self) |
| Create/edit workout plans | ✅ | ✅ | ❌ | ✅ (own) | ❌ | ❌ |
| **Diet Plans** | | | | | | |
| View diet plans | ✅ | ✅ | ✅ | ❌ | ✅ (own) | ✅ (self) |
| Create/edit diet plans | ✅ | ✅ | ❌ | ❌ | ✅ (own) | ❌ |
| **Dashboard** | | | | | | |
| View dashboard | ✅ | ✅ | ✅ | ✅ (limited) | ❌ | ❌ |
| **Reports** | | | | | | |
| View reports | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 3. Database Schema

### RolePermission Model (Optional — for custom per-tenant role overrides)

```python
# permissions/models.py

from django.db import models
from tenants.models import TenantModelMixin, Tenant


class Role(models.Model):
    """Defines a role within the system. Core roles are seeded; tenants can add custom roles."""

    class CoreRole(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform Admin"
        GYM_OWNER = "gym_owner", "Gym Owner"
        MANAGER = "manager", "Manager"
        TRAINER = "trainer", "Trainer"
        DIETITIAN = "dietitian", "Dietitian"
        CUSTOMER = "customer", "Customer"

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=True)  # system roles can't be deleted
    is_tenant_custom = models.BooleanField(default=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roles"
        ordering = ["id"]
        constraints = [
            # Tenant-scoped custom roles must be unique per tenant
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=models.Q(is_tenant_custom=True),
                name="uq_role_tenant_code_custom",
            ),
            # System roles must be globally unique
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(is_tenant_custom=False),
                name="uq_role_code_system",
            ),
        ]


class Permission(models.Model):
    """Defines a granular permission. Permissions are app-level + action + resource."""

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=100, unique=True)  # e.g., "branches.create_branch"
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    app_label = models.CharField(max_length=50)  # "branches", "customers", etc.
    action = models.CharField(max_length=20)  # "view", "create", "edit", "delete"
    resource = models.CharField(max_length=50)  # "branch", "customer", etc.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permissions"
        ordering = ["app_label", "resource", "action"]
        unique_together = ["app_label", "action", "resource"]


class RolePermission(models.Model):
    """Maps permissions to roles (M2M). System roles have fixed permissions; custom roles are editable."""

    id = models.BigAutoField(primary_key=True)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="permission_roles")
    is_granted = models.BooleanField(default=True)  # True=allow, False=deny
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_permissions"
        unique_together = ["role", "permission"]


class UserRoleAssignment(models.Model):
    """Assigns a role to a user. Used for custom roles; core roles use User.role field directly."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_assignments")
    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="role_assignments",
                               help_text="For branch-scoped roles (e.g., manager of a specific branch)")
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="assigned_roles")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_role_assignments"
        ordering = ["-assigned_at"]
```

### SQL

```sql
CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    is_system_role BOOLEAN NOT NULL DEFAULT TRUE,
    is_tenant_custom BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_role_tenant_code_custom ON roles(tenant_id, code) WHERE is_tenant_custom = TRUE;
CREATE UNIQUE INDEX uq_role_code_system ON roles(code) WHERE is_tenant_custom = FALSE;

CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    app_label VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL,
    resource VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(app_label, action, resource)
);

CREATE TABLE role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    is_granted BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(role_id, permission_id)
);

CREATE TABLE user_role_assignments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    branch_id BIGINT,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by_id BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_ura_user ON user_role_assignments(user_id, is_active);
CREATE INDEX idx_ura_branch ON user_role_assignments(branch_id, is_active);
```

### Seed Data

```sql
-- Seed core roles
INSERT INTO roles (code, name, is_system_role, is_tenant_custom) VALUES
  ('platform_admin', 'Platform Admin', TRUE, FALSE),
  ('gym_owner', 'Gym Owner', TRUE, FALSE),
  ('manager', 'Manager', TRUE, FALSE),
  ('trainer', 'Trainer', TRUE, FALSE),
  ('dietitian', 'Dietitian', TRUE, FALSE),
  ('customer', 'Customer', TRUE, FALSE);

-- Seed permissions (examples — full list generated by management command)
INSERT INTO permissions (code, name, app_label, action, resource) VALUES
  ('tenants.view_tenant', 'View tenant', 'tenants', 'view', 'tenant'),
  ('tenants.edit_tenant', 'Edit tenant settings', 'tenants', 'edit', 'tenant'),
  ('branches.view_branch', 'View branches', 'branches', 'view', 'branch'),
  ('branches.create_branch', 'Create branch', 'branches', 'create', 'branch'),
  ('branches.edit_branch', 'Edit branch', 'branches', 'edit', 'branch'),
  ('branches.delete_branch', 'Delete/deactivate branch', 'branches', 'delete', 'branch'),
  ('customers.view_customer', 'View customers', 'customers', 'view', 'customer'),
  ('customers.create_customer', 'Create customer', 'customers', 'create', 'customer'),
  ('customers.edit_customer', 'Edit customer', 'customers', 'edit', 'customer'),
  ('customers.delete_customer', 'Delete customer', 'customers', 'delete', 'customer'),
  ('users.view_user', 'View users', 'users', 'view', 'user'),
  ('users.create_user', 'Create user', 'users', 'create', 'user'),
  ('users.edit_user', 'Edit user', 'users', 'edit', 'user'),
  ('users.delete_user', 'Deactivate user', 'users', 'delete', 'user'),
  ('memberships.view_membership', 'View memberships', 'memberships', 'view', 'membership'),
  ('memberships.create_membership', 'Create membership', 'memberships', 'create', 'membership'),
  ('memberships.edit_membership', 'Edit membership', 'memberships', 'edit', 'membership'),
  ('payments.view_payment', 'View payments', 'payments', 'view', 'payment'),
  ('payments.record_payment', 'Record payment', 'payments', 'create', 'payment'),
  ('attendance.view_attendance', 'View attendance', 'attendance', 'view', 'attendance'),
  ('attendance.log_attendance', 'Log attendance', 'attendance', 'create', 'attendance'),
  ('workouts.view_workout', 'View workout plans', 'workouts', 'view', 'workout'),
  ('workouts.create_workout', 'Create workout plan', 'workouts', 'create', 'workout'),
  ('workouts.edit_workout', 'Edit workout plan', 'workouts', 'edit', 'workout'),
  ('diets.view_diet', 'View diet plans', 'diets', 'view', 'diet'),
  ('diets.create_diet', 'Create diet plan', 'diets', 'create', 'diet'),
  ('diets.edit_diet', 'Edit diet plan', 'diets', 'edit', 'diet'),
  ('reports.view_report', 'View reports', 'reports', 'view', 'report'),
  ('dashboard.view_dashboard', 'View dashboard', 'dashboard', 'view', 'dashboard');

-- Map permissions to roles (RolePermission)
-- Platform Admin: ALL permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = 'platform_admin';

-- Gym Owner: all tenant-scoped permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'gym_owner' AND p.code != 'tenants.view_tenant';

-- Manager: branch, customer, membership, payment, attendance operations
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'manager' AND p.code IN (
  'branches.view_branch',
  'customers.view_customer', 'customers.create_customer', 'customers.edit_customer',
  'users.view_user', 'users.create_user', 'users.edit_user',
  'memberships.view_membership', 'memberships.create_membership', 'memberships.edit_membership',
  'payments.view_payment', 'payments.record_payment',
  'attendance.view_attendance', 'attendance.log_attendance',
  'dashboard.view_dashboard', 'reports.view_report'
);

-- Trainer: view/create/edit workout plans, view assigned customers, log attendance
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'trainer' AND p.code IN (
  'customers.view_customer',
  'memberships.view_membership',
  'attendance.view_attendance', 'attendance.log_attendance',
  'workouts.view_workout', 'workouts.create_workout', 'workouts.edit_workout',
  'dashboard.view_dashboard'
);

-- Dietitian: view/create/edit diet plans, view assigned customers
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'dietitian' AND p.code IN (
  'customers.view_customer',
  'diets.view_diet', 'diets.create_diet', 'diets.edit_diet'
);

-- Customer: self-service only
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'customer' AND p.code IN (
  'memberships.view_membership',
  'payments.view_payment',
  'attendance.view_attendance', 'attendance.log_attendance',
  'workouts.view_workout',
  'diets.view_diet'
);
```

---

## 4. DRF Permission Classes

```python
# permissions/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied


class IsPlatformAdmin(BasePermission):
    """Only platform admins (superusers)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class IsTenantMember(BasePermission):
    """User must belong to the request's tenant."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.tenant is not None and request.user.tenant_id == request.tenant.id


class RolePermission(BasePermission):
    """
    Permission class that checks the user's role against the required permission.

    Usage in views:
        permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
        required_permission = "branches.create_branch"  # set per-view

    Or use the mixin:
        class BranchCreateView(RolePermissionMixin, APIView):
            required_permission = "branches.create_branch"
    """

    # Map core roles to permission codes for quick lookup
    ROLE_PERMISSION_MATRIX = {
        "platform_admin": "*",  # all permissions
        "gym_owner": "*",       # all tenant-scoped permissions
        "manager": {
            "branches.view_branch", "customers.view_customer", "customers.create_customer",
            "customers.edit_customer", "users.view_user", "users.create_user", "users.edit_user",
            "memberships.view_membership", "memberships.create_membership", "memberships.edit_membership",
            "payments.view_payment", "payments.record_payment",
            "attendance.view_attendance", "attendance.log_attendance",
            "dashboard.view_dashboard", "reports.view_report",
        },
        "trainer": {
            "customers.view_customer", "memberships.view_membership",
            "attendance.view_attendance", "attendance.log_attendance",
            "workouts.view_workout", "workouts.create_workout", "workouts.edit_workout",
            "dashboard.view_dashboard",
        },
        "dietitian": {
            "customers.view_customer",
            "diets.view_diet", "diets.create_diet", "diets.edit_diet",
        },
        "customer": {
            "memberships.view_membership", "payments.view_payment",
            "attendance.view_attendance", "attendance.log_attendance",
            "workouts.view_workout", "diets.view_diet",
        },
    }

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Platform admins have all permissions
        if request.user.is_superuser:
            return True

        required = getattr(view, "required_permission", None)
        if required is None:
            return True  # no specific permission required

        user_role = request.user.role
        allowed = self.ROLE_PERMISSION_MATRIX.get(user_role, set())

        if allowed == "*":
            return True

        return required in allowed

    def has_object_permission(self, request, view, obj):
        """
        Object-level permission: ensure the object belongs to the user's tenant.
        For customers/trainers, additionally check if they're assigned to this user.
        """
        if request.user.is_superuser:
            return True

        # Object must belong to the same tenant
        if hasattr(obj, "tenant_id") and obj.tenant_id != request.user.tenant_id:
            return False

        # Customer can only access their own records
        if request.user.role == "customer":
            if hasattr(obj, "user_id") and obj.user_id != request.user.id:
                return False
            if hasattr(obj, "customer_id"):
                # Check if this customer record belongs to this user
                from customers.models import Customer
                try:
                    Customer.objects.get(id=obj.customer_id, user_id=request.user.id)
                except Customer.DoesNotExist:
                    return False

        # Trainer can only access customers assigned to them
        if request.user.role == "trainer" and hasattr(obj, "trainer_id"):
            if obj.trainer_id != request.user.trainer_profile.id:
                return False

        return True


class RolePermissionMixin:
    """Mixin for APIView / ViewSet to set required_permission."""

    required_permission = None
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]

    def get_permissions(self):
        # You can override per-action
        if self.action in ["list", "retrieve"]:
            self.required_permission = self.required_permission.replace("create_", "view_").replace("edit_", "view_").replace("delete_", "view_")
        return super().get_permissions()
```

---

## 5. Token Authentication with Tenant Context

### Token Model (Extended)

```python
# users/auth.py

import uuid
from django.db import models
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token as DRFToken


class AuthToken(models.Model):
    """
    Extended token model with tenant context and device info.
    Replaces DRF's default Token for richer context.
    """

    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="auth_tokens",
        help_text="Tenant context for this token. Null for platform admins.",
    )
    device_id = models.CharField(max_length=200, blank=True, help_text="Device identifier (mobile)")
    device_type = models.CharField(max_length=20, blank=True, choices=[
        ("web", "Web"), ("ios", "iOS"), ("android", "Android")
    ])
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_tokens"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key():
        return uuid.uuid4().hex + uuid.uuid4().hex  # 64-char token

    def __str__(self):
        return f"{self.user.email} — {self.device_type or 'web'}"
```

### Token Authentication Backend

```python
# users/authentication.py

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from users.auth import AuthToken
from tenants.models import Tenant


class TenantTokenAuthentication(BaseAuthentication):
    """
    DRF authentication backend that reads the token from Authorization header,
    resolves the user AND the tenant context.
    """

    keyword = "Token"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(self.keyword):
            return None

        token_key = auth_header[len(self.keyword):].strip()
        try:
            token = AuthToken.objects.select_related("user", "tenant").get(
                key=token_key, is_active=True
            )
        except AuthToken.DoesNotExist:
            raise AuthenticationFailed("Invalid or expired token")

        if token.expires_at and timezone.now() > token.expires_at:
            raise AuthenticationFailed("Token expired")

        # Update last used
        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at"])

        # Attach tenant to the request (used by TenantMiddleware)
        user = token.user
        user._tenant_from_token = token.tenant  # used by middleware

        return (user, token)
```

### Updated TenantMiddleware

```python
# tenants/middleware.py (updated for token-based tenant resolution)

class TenantMiddleware:
    """
    Resolves tenant from either:
    1. AuthToken's tenant field (set during login)
    2. User's tenant_id (fallback)
    3. ?tenant_id= query param (platform admin impersonation)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        if hasattr(request, "user") and request.user.is_authenticated:
            # Priority 1: tenant from token (set by TenantTokenAuthentication)
            if hasattr(request.user, "_tenant_from_token"):
                request.tenant = request.user._tenant_from_token
            # Priority 2: platform admin impersonation
            elif request.user.is_superuser:
                tenant_id = request.GET.get("tenant_id") or request.headers.get("X-Tenant-ID")
                if tenant_id:
                    try:
                        request.tenant = Tenant.objects.get(id=int(tenant_id))
                    except (Tenant.DoesNotExist, ValueError):
                        pass
            # Priority 3: user's own tenant
            elif request.user.tenant_id:
                request.tenant = request.user.tenant

        response = self.get_response(request)
        return response
```

---

## 6. Login & Token Issuance API

### 6.1 Login

```
POST /api/v1/auth/login/
```

**Request:**
```json
{
  "email": "arjun@ironpeak.com",
  "password": "SecurePass123!",
  "device_type": "web"  // or "ios", "android"
}
```

**Response (200):**
```json
{
  "token": "a1b2c3d4e5f6...",
  "user": {
    "id": 1,
    "email": "arjun@ironpeak.com",
    "name": "Arjun Kumar",
    "role": "gym_owner",
    "tenant_id": 17,
    "tenant_name": "Iron Peak Gym",
    "is_owner": true
  },
  "permissions": [
    "branches.create_branch",
    "branches.view_branch",
    "customers.create_customer",
    ...
  ]
}
```

**Side effects:**
- Validate credentials (email + password)
- Validate user's tenant status is `ACTIVE` (not suspended/cancelled)
- Create `AuthToken` with tenant context
- Return token + user info + permissions list

### 6.2 Logout

```
POST /api/v1/auth/logout/
Authorization: Token <token>
```

Deactivates the current token.

### 6.3 Get Current User

```
GET /api/v1/auth/me/
Authorization: Token <token>
```

Returns user profile, role, tenant info, and permissions list.

### 6.4 OTP Login (for mobile app customers)

```
POST /api/v1/auth/otp/request/
```
**Request:**
```json
{ "phone": "+919876543210" }
```

```
POST /api/v1/auth/otp/verify/
```
**Request:**
```json
{ "phone": "+919876543210", "otp": "123456", "device_type": "android" }
```

**Response (200):**
```json
{
  "token": "a1b2c3d4...",
  "user": {
    "id": 42,
    "email": "raman@example.com",
    "name": "Raman Nair",
    "role": "customer",
    "tenant_id": 17,
    "tenant_name": "Iron Peak Gym",
    "branch_id": 1,
    "branch_name": "Kochi Main"
  },
  "permissions": [
    "memberships.view_membership",
    "payments.view_payment",
    "attendance.view_attendance",
    "attendance.log_attendance",
    "workouts.view_workout",
    "diets.view_diet"
  ]
}
```

---

## 7. User Management API

### 7.1 List Users (gym_owner, manager only)

```
GET /api/v1/users/
Authorization: Token <token>
```

**Query params:** `?role=trainer`, `?branch_id=1`, `?is_active=true`, `?search=`

### 7.2 Create User

```
POST /api/v1/users/
Authorization: Token <token>
```

**Request:**
```json
{
  "email": "rahul@ironpeak.com",
  "first_name": "Rahul",
  "last_name": "Sharma",
  "phone": "+919876543210",
  "role": "trainer",
  "branch_id": 1,
  "send_invite": true
}
```

**Response (201):**
```json
{
  "id": 5,
  "email": "rahul@ironpeak.com",
  "role": "trainer",
  "message": "User created and invite email sent"
}
```

**Validation:**
- Only gym_owner and manager can create users
- Manager can only create trainer/dietitian/customer users (not other managers or owners)
- Role assignment checks the permission matrix
- If `send_invite=true`, an email with a password setup link is sent

### 7.3 Update User Role

```
PATCH /api/v1/users/{id}/
Authorization: Token <token>
```

**Request:**
```json
{
  "role": "manager",
  "is_active": false
}
```

### 7.4 Assign User to Branch

```
POST /api/v1/users/{id}/assign-branch/
Authorization: Token <token>
```

**Request:**
```json
{ "branch_id": 2, "role_at_branch": "manager" }
```

---

## 8. Frontend Route Guards (Next.js)

```typescript
// lib/permissions.ts

export const ROLE_PERMISSIONS: Record<string, Set<string>> = {
  platform_admin: new Set(["*"]),
  gym_owner: new Set(["*"]),
  manager: new Set([
    "branches.view_branch", "customers.view_customer", "customers.create_customer",
    "customers.edit_customer", "users.view_user", "users.create_user", "users.edit_user",
    "memberships.view_membership", "memberships.create_membership", "memberships.edit_membership",
    "payments.view_payment", "payments.record_payment",
    "attendance.view_attendance", "attendance.log_attendance",
    "dashboard.view_dashboard", "reports.view_report",
  ]),
  trainer: new Set([
    "customers.view_customer", "memberships.view_membership",
    "attendance.view_attendance", "attendance.log_attendance",
    "workouts.view_workout", "workouts.create_workout", "workouts.edit_workout",
    "dashboard.view_dashboard",
  ]),
  dietitian: new Set([
    "customers.view_customer",
    "diets.view_diet", "diets.create_diet", "diets.edit_diet",
  ]),
  customer: new Set([
    "memberships.view_membership", "payments.view_payment",
    "attendance.view_attendance", "attendance.log_attendance",
    "workouts.view_workout", "diets.view_diet",
  ]),
};

export function hasPermission(userRole: string, permission: string): boolean {
  const perms = ROLE_PERMISSIONS[userRole];
  if (!perms) return false;
  if (perms.has("*")) return true;
  return perms.has(permission);
}

// Middleware to protect routes
export function requirePermission(permission: string) {
  return (ctx: NextPageContext) => {
    const user = getUserFromSession(ctx);
    if (!user || !hasPermission(user.role, permission)) {
      return { redirect: { destination: "/unauthorized", permanent: false } };
    }
  };
}
```

---

## 9. Management Command: Seed Permissions

```python
# permissions/management/commands/seed_permissions.py

from django.core.management.base import BaseCommand
from permissions.models import Role, Permission, RolePermission


class Command(BaseCommand):
    help = "Seeds roles, permissions, and role-permission mappings."

    def handle(self, *args, **options):
        # Seed roles
        for code, name in Role.CoreRole.choices:
            Role.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_system_role": True, "is_tenant_custom": False}
            )

        # Seed permissions (generated from registry)
        PERMISSION_REGISTRY = [
            ("tenants", "view", "tenant", "View tenant"),
            ("tenants", "edit", "tenant", "Edit tenant settings"),
            ("branches", "view", "branch", "View branches"),
            ("branches", "create", "branch", "Create branch"),
            ("branches", "edit", "branch", "Edit branch"),
            ("branches", "delete", "branch", "Delete/deactivate branch"),
            ("customers", "view", "customer", "View customers"),
            ("customers", "create", "customer", "Create customer"),
            ("customers", "edit", "customer", "Edit customer"),
            ("customers", "delete", "customer", "Delete customer"),
            ("users", "view", "user", "View users"),
            ("users", "create", "user", "Create user"),
            ("users", "edit", "user", "Edit user"),
            ("users", "delete", "user", "Deactivate user"),
            ("memberships", "view", "membership", "View memberships"),
            ("memberships", "create", "membership", "Create membership"),
            ("memberships", "edit", "membership", "Edit membership"),
            ("payments", "view", "payment", "View payments"),
            ("payments", "create", "payment", "Record payment"),
            ("attendance", "view", "attendance", "View attendance"),
            ("attendance", "create", "attendance", "Log attendance"),
            ("workouts", "view", "workout", "View workout plans"),
            ("workouts", "create", "workout", "Create workout plan"),
            ("workouts", "edit", "workout", "Edit workout plan"),
            ("diets", "view", "diet", "View diet plans"),
            ("diets", "create", "diet", "Create diet plan"),
            ("diets", "edit", "diet", "Edit diet plan"),
            ("reports", "view", "report", "View reports"),
            ("dashboard", "view", "dashboard", "View dashboard"),
        ]

        for app, action, resource, name in PERMISSION_REGISTRY:
            code = f"{app}.{action}_{resource}"
            Permission.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "app_label": app,
                    "action": action,
                    "resource": resource,
                }
            )

        # Map permissions to roles (from matrix above)
        ROLE_MATRIX = {
            "platform_admin": "*",
            "gym_owner": "*",
            "manager": [
                "branches.view_branch",
                "customers.view_customer", "customers.create_customer", "customers.edit_customer",
                "users.view_user", "users.create_user", "users.edit_user",
                "memberships.view_membership", "memberships.create_membership", "memberships.edit_membership",
                "payments.view_payment", "payments.create_payment",
                "attendance.view_attendance", "attendance.create_attendance",
                "dashboard.view_dashboard", "reports.view_report",
            ],
            "trainer": [
                "customers.view_customer",
                "memberships.view_membership",
                "attendance.view_attendance", "attendance.create_attendance",
                "workouts.view_workout", "workouts.create_workout", "workouts.edit_workout",
                "dashboard.view_dashboard",
            ],
            "dietitian": [
                "customers.view_customer",
                "diets.view_diet", "diets.create_diet", "diets.edit_diet",
            ],
            "customer": [
                "memberships.view_membership",
                "payments.view_payment",
                "attendance.view_attendance", "attendance.create_attendance",
                "workouts.view_workout",
                "diets.view_diet",
            ],
        }

        for role_code, perm_codes in ROLE_MATRIX.items():
            role = Role.objects.get(code=role_code)
            if perm_codes == "*":
                # Grant all permissions
                for perm in Permission.objects.all():
                    RolePermission.objects.get_or_create(
                        role=role, permission=perm, defaults={"is_granted": True}
                    )
            else:
                for code in perm_codes:
                    try:
                        perm = Permission.objects.get(code=code)
                        RolePermission.objects.get_or_create(
                            role=role, permission=perm, defaults={"is_granted": True}
                        )
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Permission not found: {code}"))

        self.stdout.write(self.style.SUCCESS("Permissions seeded successfully."))
```

---

## 10. Implementation Checklist

| # | Task | Owner | Status |
|---|------|-------|--------|
| 1 | Create `permissions` Django app | Backend | ☐ |
| 2 | Implement `Role`, `Permission`, `RolePermission` models | Backend | ☐ |
| 3 | Implement `UserRoleAssignment` model | Backend | ☐ |
| 4 | Implement `AuthToken` model (extended token) | Backend | ☐ |
| 5 | Implement `TenantTokenAuthentication` backend | Backend | ☐ |
| 6 | Implement `RolePermission` DRF permission class | Backend | ☐ |
| 7 | Update `TenantMiddleware` for token-based tenant resolution | Backend | ☐ |
| 8 | Implement login/logout/me API endpoints | Backend | ☐ |
| 9 | Implement OTP request/verify endpoints (mobile) | Backend | ☐ |
| 10 | Implement user management CRUD API | Backend | ☐ |
| 11 | Run `seed_permissions` management command | Backend | ☐ |
| 12 | Write tests: role-based access, tenant isolation, token auth | Backend | ☐ |
| 13 | Frontend: route guards + permission checks | Frontend | ☐ |
| 14 | Frontend: user management UI (role assignment) | Frontend | ☐ |
| 15 | Mobile: OTP auth flow | Mobile | ☐ |

---

## 11. Cross-Story Dependencies

- **Requires:** FBOS-010 (Tenant model, middleware), FBOS-001 (User model with role + tenant_id)
- **Required by:** ALL stories — every API endpoint uses `RolePermission` for authorization
- **Required by:** FBOS-002 (branch CRUD requires `branches.create_branch` permission)
- **Required by:** FBOS-003 (customer CRUD requires `customers.create_customer` permission)
- **Required by:** FBOS-006 (attendance requires `attendance.log_attendance` permission)
- **Future:** Custom roles per tenant, branch-scoped roles, permission overrides