# FBOS-001: Vendor Registration & Onboarding

## Overview

Defines the end-to-end flow for a gym owner to register their business on FBOS, verify their email, select a subscription plan, and get a provisioned tenant workspace.

**Depends on:** FBOS-010 (Multi-Tenant Architecture) — uses `Tenant`, `TenantSettings`, `provision_tenant()`
**Tenant provisioning creates:** 1 Tenant + 1 TenantSettings + 1 owner User (gym_owner role)

---

## 1. Registration Flow (State Machine)

```
[Anonymous Visitor]
       |
       v
  ┌─────────────┐     submit      ┌──────────────┐     verify email    ┌──────────────┐
  │ Signup Form  │ ──────────────▶ │ Pending Email │ ──────────────────▶ │ Email Verified │
  │ (Step 1)    │                 │ Verification  │                    │               │
  └─────────────┘                 └──────────────┘                    └───────┬───────┘
       │                                                                      │
       │ email already exists → error                                        │
       │                                                                      v
       │                              ┌──────────────┐     confirm          ┌──────────────┐
       │                              │ Plan Selection │ ────────────────▶ │ Provisioned   │
       │                              │ (Step 2)     │                    │ + Onboard     │
       │                              └──────────────┘                    └──────────────┘
       │                                                                      │
       v                                                                      v
  [Error / Redirect]                                               [Tenant Workspace Ready]
```

### States

| State | Description | Next Action |
|-------|-------------|-------------|
| `STARTED` | User filled signup form, account created but unverified | User clicks email link |
| `EMAIL_VERIFIED` | Email confirmed, user can pick a plan | User selects plan |
| `PLAN_SELECTED` | Plan chosen, workspace provisioning triggered | System provisions tenant |
| `PROVISIONED` | Tenant + settings + owner user created | Redirect to onboarding wizard |
| `ONBOARDED` | Onboarding wizard completed | Redirect to ERP dashboard |

---

## 2. Database Schema

### Registration Model (tracks signup state)

```python
# vendors/models.py

import uuid
from django.db import models
from django.contrib.auth.hashers import make_password


class VendorRegistration(models.Model):
    """Tracks the vendor registration process until provisioning is complete."""

    class Step(models.TextChoices):
        STARTED = "started", "Started"
        EMAIL_VERIFIED = "email_verified", "Email Verified"
        PLAN_SELECTED = "plan_selected", "Plan Selected"
        PROVISIONED = "provisioned", "Provisioned"
        ONBOARDED = "onboarded", "Onboarded"

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True)
    business_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    contact_phone = models.CharField(max_length=20, blank=True)
    password_hash = models.CharField(max_length=128)  # hashed at signup
    selected_plan = models.CharField(
        max_length=20,
        choices=[("starter", "Starter"), ("professional", "Professional"), ("enterprise", "Enterprise")],
        blank=True,
    )
    email_verification_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    current_step = models.CharField(max_length=20, choices=Step.choices, default=Step.STARTED)
    provisioned_tenant_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vendor_registrations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business_name} ({self.email}) — {self.current_step}"
```

### Subscription Plan Model

```python
# vendors/models.py (continued)

class SubscriptionPlan(models.Model):
    """Defines the available subscription tiers and their features."""

    class PlanCode(models.TextChoices):
        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=20, choices=PlanCode.choices, unique=True)
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_branches = models.PositiveIntegerField()
    max_customers = models.PositiveIntegerField()
    max_trainers = models.PositiveIntegerField()
    features = models.JSONField(default=dict)  # {"whatsapp": false, "ai_coach": false, ...}
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_plans"
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.name} — ₹{self.price_monthly}/mo"
```

### SQL

```sql
CREATE TABLE vendor_registrations (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(254) NOT NULL UNIQUE,
    business_name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(200) NOT NULL,
    contact_phone VARCHAR(20) DEFAULT '',
    password_hash VARCHAR(128) NOT NULL,
    selected_plan VARCHAR(20) DEFAULT '',
    email_verification_token UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    email_verified_at TIMESTAMPTZ,
    current_step VARCHAR(20) NOT NULL DEFAULT 'started',
    provisioned_tenant_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vendor_registrations_step ON vendor_registrations(current_step);

CREATE TABLE subscription_plans (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    price_monthly DECIMAL(10,2) NOT NULL,
    price_yearly DECIMAL(10,2) NOT NULL,
    max_branches INTEGER NOT NULL,
    max_customers INTEGER NOT NULL,
    max_trainers INTEGER NOT NULL,
    features JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed initial plans
INSERT INTO subscription_plans (code, name, price_monthly, price_yearly, max_branches, max_customers, max_trainers, features, sort_order)
VALUES
  ('starter', 'Starter', 999.00, 9990.00, 1, 100, 5, '{"whatsapp": false, "ai_coach": false, "custom_branding": false}', 1),
  ('professional', 'Professional', 2999.00, 29990.00, 5, 1000, 50, '{"whatsapp": true, "ai_coach": false, "custom_branding": true}', 2),
  ('enterprise', 'Enterprise', 9999.00, 99990.00, 50, 10000, 500, '{"whatsapp": true, "ai_coach": true, "custom_branding": true}', 3);
```

---

## 3. User Model (Tenant-Aware)

The User model extends Django's AbstractUser with `tenant_id` and `role`.

```python
# users/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from tenants.models import Tenant


class User(AbstractUser):
    """Tenant-aware user. Platform admins have tenant_id=NULL."""

    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform Admin"
        GYM_OWNER = "gym_owner", "Gym Owner"
        MANAGER = "manager", "Manager"
        TRAINER = "trainer", "Trainer"
        DIETITIAN = "dietitian", "Dietitian"
        CUSTOMER = "customer", "Customer"

    # Override username to use email as the login identifier
    username = None  # remove username field
    email = models.EmailField(unique=False)  # unique per-tenant, enforced by DB constraint
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,  # null for platform admins
        blank=True,
        related_name="users",
        db_index=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=20, blank=True)
    is_owner = models.BooleanField(default=False)  # True for the vendor's owner account
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"  # login with email
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        constraints = [
            # Email must be unique within a tenant (not globally — same person can be in multiple gyms)
            models.UniqueConstraint(
                fields=["tenant", "email"],
                name="uq_user_tenant_email",
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"
```

---

## 4. API Endpoints

### 4.1 Signup (Step 1)

```
POST /api/v1/auth/signup/
```

**Request:**
```json
{
  "business_name": "Iron Peak Gym",
  "contact_name": "Arjun Kumar",
  "email": "arjun@ironpeak.com",
  "phone": "+919876543210",
  "password": "SecurePass123!"
}
```

**Response (201):**
```json
{
  "registration_id": 42,
  "message": "Verification email sent to arjun@ironpeak.com",
  "next_step": "verify_email"
}
```

**Validation:**
- `email` — must not exist in `vendor_registrations` where `current_step` != `STARTED` (i.e., previous abandoned attempts can re-register)
- `email` — must not exist in `users` where `is_owner=True` (already a gym owner)
- `business_name` — 2–200 chars
- `password` — min 8 chars, at least 1 uppercase, 1 digit

**Side effects:**
- Create `VendorRegistration` with `password_hash` (Django make_password)
- Generate `email_verification_token`
- Send verification email with link: `{FRONTEND_URL}/verify-email?token={token}`

### 4.2 Email Verification

```
GET /api/v1/auth/verify-email/?token={uuid}
```

**Response (200):**
```json
{
  "message": "Email verified successfully",
  "registration_id": 42,
  "next_step": "select_plan"
}
```

**Response (400 — invalid/expired):**
```json
{
  "error": "Invalid or expired verification token"
}
```

**Side effects:**
- Set `email_verified_at = NOW()`
- Update `current_step = EMAIL_VERIFIED`

### 4.3 Resend Verification Email

```
POST /api/v1/auth/resend-verification/
```

**Request:**
```json
{ "email": "arjun@ironpeak.com" }
```

**Response (200):**
```json
{ "message": "Verification email re-sent" }
```

### 4.4 Get Subscription Plans

```
GET /api/v1/subscriptions/plans/
```

**Response (200):**
```json
{
  "plans": [
    {
      "code": "starter",
      "name": "Starter",
      "price_monthly": "999.00",
      "price_yearly": "9990.00",
      "max_branches": 1,
      "max_customers": 100,
      "max_trainers": 5,
      "features": { "whatsapp": false, "ai_coach": false, "custom_branding": false }
    },
    {
      "code": "professional",
      "name": "Professional",
      "price_monthly": "2999.00",
      "price_yearly": "29990.00",
      "max_branches": 5,
      "max_customers": 1000,
      "max_trainers": 50,
      "features": { "whatsapp": true, "ai_coach": false, "custom_branding": true }
    },
    {
      "code": "enterprise",
      "name": "Enterprise",
      "price_monthly": "9999.00",
      "price_yearly": "99990.00",
      "max_branches": 50,
      "max_customers": 10000,
      "max_trainers": 500,
      "features": { "whatsapp": true, "ai_coach": true, "custom_branding": true }
    }
  ]
}
```

### 4.5 Select Plan & Provision (Step 2)

```
POST /api/v1/auth/select-plan/
```

**Request:**
```json
{
  "registration_id": 42,
  "plan_code": "professional"
}
```

**Response (201):**
```json
{
  "message": "Workspace provisioned successfully",
  "tenant": {
    "id": 17,
    "uuid": "a1b2c3d4-...",
    "name": "Iron Peak Gym",
    "subscription_plan": "professional"
  },
  "auth_token": "eyJhbGciOiJIUzI1NiIs...",
  "next_step": "onboarding_wizard"
}
```

**Side effects (transactional):**
1. Validate registration is in `EMAIL_VERIFIED` step
2. Call `provision_tenant()` from FBOS-010:
   - Create `Tenant` with selected plan
   - Create `TenantSettings` with plan limits
3. Create owner `User`:
   - `tenant_id = tenant.id`
   - `role = GYM_OWNER`
   - `is_owner = True`
   - `email = registration.email`
   - `first_name`, `last_name` from `contact_name`
   - `password_hash` from registration
4. Update `VendorRegistration`:
   - `current_step = PROVISIONED`
   - `provisioned_tenant_id = tenant.id`
5. Generate DRF auth token (TokenAuthentication or JWT)
6. Send welcome email

### 4.6 Onboarding Wizard Status

```
PUT /api/v1/auth/onboarding/
Authorization: Token <token>
```

**Request:**
```json
{
  "business_type": "gym",
  "branches_count": 1,
  "primary_branch_name": "Main Branch",
  "primary_branch_address": "MG Road, Kochi, Kerala",
  "primary_branch_phone": "+914841234567"
}
```

**Response (200):**
```json
{
  "message": "Onboarding completed",
  "redirect_to": "/dashboard"
}
```

**Side effects:**
- Create default branch (via FBOS-002 Branch API)
- Set `VendorRegistration.current_step = ONBOARDED`
- Optionally: create sample membership plans, import default exercise library

---

## 5. DRF Serializers

```python
# vendors/serializers.py

from rest_framework import serializers
from vendors.models import VendorRegistration, SubscriptionPlan


class SignupSerializer(serializers.Serializer):
    business_name = serializers.CharField(min_length=2, max_length=200)
    contact_name = serializers.CharField(min_length=2, max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_email(self, value):
        # Check if email is already a gym owner
        if User.objects.filter(email=value, is_owner=True).exists():
            raise serializers.ValidationError("This email is already registered as a gym owner.")
        return value


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.UUIDField()


class SelectPlanSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    plan_code = serializers.ChoiceField(choices=["starter", "professional", "enterprise"])


class OnboardingSerializer(serializers.Serializer):
    business_type = serializers.ChoiceField(choices=["gym", "yoga_studio", "crossfit", "personal_training", "wellness_center"])
    branches_count = serializers.IntegerField(min_value=1, max_value=50)
    primary_branch_name = serializers.CharField(max_length=200)
    primary_branch_address = serializers.CharField(max_length=500)
    primary_branch_phone = serializers.CharField(max_length=20)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["code", "name", "price_monthly", "price_yearly", "max_branches", "max_customers", "max_trainers", "features"]
```

---

## 6. ViewSet Summary

```python
# vendors/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from tenants.services import provision_tenant
from users.models import User
from vendors.models import VendorRegistration, SubscriptionPlan
from vendors.serializers import *
from vendors.emails import send_verification_email, send_welcome_email


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        reg = VendorRegistration.objects.create(
            email=data["email"],
            business_name=data["business_name"],
            contact_name=data["contact_name"],
            contact_phone=data.get("phone", ""),
            password_hash=make_password(data["password"]),
        )
        send_verification_email(reg)
        return Response({"registration_id": reg.id, "message": "Verification email sent", "next_step": "verify_email"}, status=201)


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        try:
            reg = VendorRegistration.objects.get(email_verification_token=token, current_step=VendorRegistration.Step.STARTED)
        except VendorRegistration.DoesNotExist:
            return Response({"error": "Invalid or expired verification token"}, status=400)

        reg.email_verified_at = timezone.now()
        reg.current_step = VendorRegistration.Step.EMAIL_VERIFIED
        reg.save()
        return Response({"message": "Email verified successfully", "registration_id": reg.id, "next_step": "select_plan"})


class SelectPlanView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SelectPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        reg = VendorRegistration.objects.get(id=data["registration_id"], current_step=VendorRegistration.Step.EMAIL_VERIFIED)
        plan = SubscriptionPlan.objects.get(code=data["plan_code"], is_active=True)

        reg.selected_plan = plan.code
        reg.save()

        # Provision tenant
        tenant = provision_tenant(
            name=reg.business_name,
            contact_email=reg.email,
            subscription_plan=plan.code,
        )

        # Create owner user
        name_parts = reg.contact_name.split(" ", 1)
        user = User.objects.create(
            tenant=tenant,
            email=reg.email,
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else "",
            phone=reg.contact_phone,
            role=User.Role.GYM_OWNER,
            is_owner=True,
        )
        user.password = reg.password_hash  # already hashed
        user.save()

        # Generate token
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=user)

        reg.current_step = VendorRegistration.Step.PROVISIONED
        reg.provisioned_tenant_id = tenant.id
        reg.save()

        send_welcome_email(reg, tenant)

        return Response({
            "message": "Workspace provisioned successfully",
            "tenant": {"id": tenant.id, "uuid": str(tenant.uuid), "name": tenant.name, "subscription_plan": tenant.subscription_plan},
            "auth_token": token.key,
            "next_step": "onboarding_wizard"
        }, status=201)


class SubscriptionPlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order")
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response({"plans": serializer.data})
```

---

## 7. URL Configuration

```python
# urls.py

urlpatterns = [
    path("api/v1/auth/signup/", SignupView.as_view(), name="signup"),
    path("api/v1/auth/verify-email/", EmailVerifyView.as_view(), name="verify-email"),
    path("api/v1/auth/resend-verification/", ResendVerificationView.as_view(), name="resend-verification"),
    path("api/v1/auth/select-plan/", SelectPlanView.as_view(), name="select-plan"),
    path("api/v1/auth/onboarding/", OnboardingView.as_view(), name="onboarding"),
    path("api/v1/subscriptions/plans/", SubscriptionPlanListView.as_view(), name="subscription-plans"),
]
```

---

## 8. Email Templates

### Verification Email

```
Subject: Verify your email — FitNation FBOS

Hi {{ contact_name }},

Thank you for signing up for FitNation! Please verify your email to continue:

{{ FRONTEND_URL }}/verify-email?token={{ token }}

This link expires in 24 hours.

— FitNation Team
```

### Welcome Email

```
Subject: Welcome to FitNation, {{ business_name }}!

Hi {{ contact_name }},

Your workspace is ready! You can now access your dashboard:

{{ FRONTEND_URL }}/dashboard

Your subscription: {{ plan_name }}
Your tenant ID: {{ tenant_id }}

Next steps:
1. Set up your first gym branch
2. Add trainers
3. Start adding customers

— FitNation Team
```

---

## 9. Frontend Pages (Next.js)

| Route | Component | Auth Required | Description |
|-------|-----------|---------------|-------------|
| `/signup` | `SignUpPage` | No | Multi-field form with validation |
| `/verify-email` | `VerifyEmailPage` | No | Reads `?token=` from URL, calls API |
| `/select-plan` | `SelectPlanPage` | No (uses registration_id) | 3 plan cards with features |
| `/onboarding` | `OnboardingPage` | Yes (token) | Wizard: business type → branch info |
| `/dashboard` | `DashboardPage` | Yes | ERP dashboard (FBOS-008) |

---

## 10. Implementation Checklist

| # | Task | Owner | Status |
|---|------|-------|--------|
| 1 | Create `vendors` Django app | Backend | ☐ |
| 2 | Implement `VendorRegistration` model | Backend | ☐ |
| 3 | Implement `SubscriptionPlan` model + seed data | Backend | ☐ |
| 4 | Implement `User` model (tenant-aware) | Backend | ☐ |
| 5 | Implement SignupView + email sending | Backend | ☐ |
| 6 | Implement EmailVerifyView | Backend | ☐ |
| 7 | Implement SelectPlanView + provisioning | Backend | ☐ |
| 8 | Implement OnboardingView | Backend | ☐ |
| 9 | Write tests: signup → verify → plan → provision flow | Backend | ☐ |
| 10 | Frontend: `/signup` page | Frontend | ☐ |
| 11 | Frontend: `/verify-email` page | Frontend | ☐ |
| 12 | Frontend: `/select-plan` page | Frontend | ☐ |
| 13 | Frontend: `/onboarding` wizard page | Frontend | ☐ |
| 14 | Integration test: end-to-end onboarding | Backend + Frontend | ☐ |

---

## 11. Cross-Story Dependencies

- **Requires:** FBOS-010 (Tenant model, `provision_tenant()`, `TenantModelMixin`)
- **Required by:** FBOS-002 (needs tenant + owner user to exist before branches can be created)
- **Required by:** FBOS-009 (User model with `role` and `tenant_id` is created here)
- **Required by:** All subsequent stories (tenant must exist before any tenant-scoped data)