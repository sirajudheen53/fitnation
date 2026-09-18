"""Access app read selectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.db.models import QuerySet

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
    from django.utils import timezone

    # 1. Check for a valid owner override first
    now = timezone.now()
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

    # 2. Default: check membership plan status. Cancelled memberships are
    # sticky (never auto-recomputed), so exclude them explicitly; time-based
    # expiry is evaluated against end_date so stale status values don't matter.
    membership = (
        customer.memberships.filter(plan__is_active=True)
        .exclude(status="cancelled")
        .select_related("plan")
        .first()
    )
    if membership is None:
        return {
            "allowed": False,
            "source": "no_membership",
            "reason": "No active membership at this branch",
        }

    today = timezone.localdate()
    plan_expiry = membership.end_date
    if plan_expiry and plan_expiry < today:
        return {
            "allowed": False,
            "source": "plan_expired",
            "reason": f"Membership plan expired on {plan_expiry}",
        }

    return {
        "allowed": True,
        "source": "plan_active",
        "reason": f"Plan valid until {plan_expiry or 'N/A'}",
    }


def get_device_allow_list(*, device: BiometricDevice) -> list[BiometricCredential]:
    """Resolve the credentials that should be on the device allow-list.

    Active credentials whose customer currently passes the access rule
    engine (active plan, no active DENY override; ALLOW overrides survive
    plan expiry).

    Args:
        device: The biometric device to resolve the allow-list for.

    Returns:
        A list of ``BiometricCredential`` instances to push to the device.
    """
    credentials = list(
        BiometricCredential.objects.for_tenant(device.tenant)
        .filter(device=device, is_active=True)
        .select_related("customer")
    )
    return [
        credential
        for credential in credentials
        if get_customer_access_state(customer=credential.customer, device=device)["allowed"]
    ]
