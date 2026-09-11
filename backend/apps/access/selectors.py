"""Access app read selectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
)

if TYPE_CHECKING:
    from apps.branches.models import Branch
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant


def list_devices(*, tenant: Tenant, branch: Branch | None = None) -> QuerySet[BiometricDevice]:
    """List active biometric devices for a tenant, optionally filtered by branch."""
    qs = BiometricDevice.objects.for_tenant(tenant).filter(is_active=True)
    if branch is not None:
        qs = qs.filter(branch=branch)
    return qs.select_related("branch")


def list_credentials(*, tenant: Tenant, device: BiometricDevice | None = None) -> QuerySet[BiometricCredential]:
    """List credentials for a tenant, optionally filtered by device."""
    qs = BiometricCredential.objects.for_tenant(tenant).filter(is_active=True)
    if device is not None:
        qs = qs.filter(device=device)
    return qs.select_related("device", "customer")


def get_customer_credentials(*, customer: Customer) -> QuerySet[BiometricCredential]:
    """List all credentials for a customer."""
    return BiometricCredential.objects.filter(customer=customer).select_related("device")


def list_access_logs(*, tenant: Tenant, device: BiometricDevice | None = None) -> QuerySet[AccessLog]:
    """List access logs for a tenant, optionally filtered by device."""
    qs = AccessLog.objects.for_tenant(tenant).select_related("device", "customer")
    if device is not None:
        qs = qs.filter(device=device)
    return qs


def list_overrides(*, tenant: Tenant, device: BiometricDevice | None = None) -> QuerySet[AccessOverride]:
    """List active access overrides for a tenant."""
    qs = AccessOverride.objects.for_tenant(tenant).select_related("device", "customer", "created_by")
    if device is not None:
        qs = qs.filter(device=device)
    return qs


def get_customer_access_state(*, customer: Customer, device: BiometricDevice) -> dict:
    """Evaluate whether a customer can access a device.

    Args:
        customer: The customer to check.
        device: The biometric device.

    Returns:
        A dict with allow/deny, source (plan/override), and reason.
    """
    # 1. Check for a valid owner override first
    now = __import__("django.utils.timezone", fromlist=["timezone"]).now()
    override = (
        AccessOverride.objects.filter(
            customer=customer,
            device=device,
        )
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        .first()
    )
    if override is not None:
        return {
            "allowed": override.allow_access,
            "source": "override",
            "reason": override.reason_notes or override.reason,
            "override_id": override.pk,
        }

    # 2. Default: check membership plan status
    membership = (
        customer.memberships.filter(plan__is_active=True)
        .select_related("plan")
        .first()
    )
    if membership is None:
        return {
            "allowed": False,
            "source": "no_membership",
            "reason": "No active membership at this branch",
        }

    plan_expiry = membership.end_date or membership.plan_expires_at
    if plan_expiry and plan_expiry < now:
        return {
            "allowed": False,
            "source": "plan_expired",
            "reason": f"Membership plan expired on {plan_expiry.date()}",
        }

    return {
        "allowed": True,
        "source": "plan_active",
        "reason": f"Plan valid until {plan_expiry.date() if plan_expiry else 'N/A'}",
    }
