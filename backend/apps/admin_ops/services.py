"""Admin ops services — platform-admin write operations (issue #40)."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.admin_ops.models import ImpersonationLog
from apps.branches.models import Branch
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token
from apps.vendors.models import SubscriptionPlan

IMPERSONATION_TOKEN_MINUTES = 30


def onboard_gym(
    *,
    gym_name: str,
    contact_name: str,
    owner_email: str,
    branch_name: str,
    plan_code: str,
    owner_phone: str = "",
    branch_type: str = "main",
) -> dict:
    """Provision a gym instantly from the admin dashboard (issue #40).

    Admin-driven onboarding: no email verification — the tenant, owner
    login, and first branch are created in one transaction, and a
    generated owner password is returned once for handover.

    Args:
        gym_name: The gym (tenant) name. Must not duplicate an existing one.
        contact_name: Owner full name (split into first/last).
        owner_email: Owner login email. Must be unique across the platform.
        branch_name: First branch name (marked as headquarters).
        plan_code: Subscription plan code (starter/professional/enterprise).
        owner_phone: Optional owner phone.
        branch_type: "main" or "sub".

    Returns:
        ``{"tenant": Tenant, "owner": User, "branch": Branch, "password": str}``
        — the plain password is returned exactly once for credential handover.

    Raises:
        ValidationError: On duplicate gym name, duplicate owner email, or
            an unknown/inactive plan code.
    """
    owner_email = owner_email.strip().lower()
    gym_name = gym_name.strip()

    if User.objects.filter(email__iexact=owner_email).exists():
        raise ValidationError({"owner_email": ["A user with this email already exists."]})
    if _gym_name_taken(gym_name):
        raise ValidationError({"gym_name": ["A gym with this name already exists."]})

    try:
        plan = SubscriptionPlan.objects.get(code=plan_code, is_active=True)
    except SubscriptionPlan.DoesNotExist as exc:
        raise ValidationError({"plan_code": ["Unknown or inactive subscription plan."]}) from exc

    with transaction.atomic():
        tenant = provision_tenant(
            name=gym_name,
            contact_email=owner_email,
            subscription_plan=plan.code,
        )
        # Admin-driven onboarding provisions PAYING gyms — active immediately
        # (provision_tenant defaults to trial, which would block owner login).
        tenant.status = Tenant.Status.ACTIVE
        tenant.save(update_fields=["status"])
        generated_password = secrets.token_urlsafe(12)
        owner = create_owner_user(
            tenant=tenant,
            email=owner_email,
            password_hash=make_password(generated_password),
            contact_name=contact_name,
            phone=owner_phone,
        )
        branch = Branch.objects.create(
            tenant=tenant,
            name=branch_name,
            branch_type=branch_type,
            is_headquarters=True,
        )

    return {"tenant": tenant, "owner": owner, "branch": branch, "password": generated_password}


def _gym_name_taken(gym_name: str) -> bool:
    """Check whether a tenant with this name already exists (case-insensitive)."""
    from apps.tenants.models import Tenant

    return Tenant.objects.filter(name__iexact=gym_name.strip()).exists()


def impersonate_owner(*, admin: User, tenant: Tenant) -> dict:
    """Issue a short-lived owner session token and audit it (issue #45).

    Args:
        admin: The authenticated platform admin requesting impersonation.
        tenant: The gym whose owner will be impersonated.

    Returns:
        ``{"owner": User, "token": AuthToken}`` — the token expires in
        ``IMPERSONATION_TOKEN_MINUTES`` minutes.

    Raises:
        NotFound: If the gym has no owner user to impersonate.
    """
    owner = (
        User.objects.filter(tenant=tenant, role=User.Role.GYM_OWNER)
        .order_by("-is_owner", "id")
        .first()
    )
    if owner is None:
        raise NotFound("This gym has no owner user to impersonate.")

    expires_at = timezone.now() + timedelta(minutes=IMPERSONATION_TOKEN_MINUTES)
    token = issue_token(owner, tenant, expires_at=expires_at)
    ImpersonationLog.objects.create(admin=admin, owner=owner, tenant=tenant, token=token)
    return {"owner": owner, "token": token}
