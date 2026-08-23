"""Tenant provisioning and read services."""

from typing import Any

from apps.tenants.models import Tenant, TenantSettings

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "starter": {"max_branches": 1, "max_customers": 100, "max_trainers": 5},
    "professional": {"max_branches": 5, "max_customers": 1000, "max_trainers": 50},
    "enterprise": {"max_branches": 50, "max_customers": 10000, "max_trainers": 500},
}


def provision_tenant(
    name: str,
    contact_email: str,
    subscription_plan: str = "starter",
    **kwargs: Any,
) -> Tenant:
    """Create a new tenant and its settings.

    Called during vendor onboarding. The created tenant is configured with plan-based
    usage limits and defaults to a trial status.

    Args:
        name: Display name of the tenant (gym business).
        contact_email: Primary contact email for the tenant. Must be unique globally.
        subscription_plan: One of ``starter``, ``professional``, ``enterprise``.
        **kwargs: Additional fields accepted by the ``Tenant`` model.

    Returns:
        The fully provisioned ``Tenant`` instance.
    """
    tenant = Tenant.objects.create(
        name=name,
        contact_email=contact_email,
        subscription_plan=subscription_plan,
        status=Tenant.Status.TRIAL,
        **kwargs,
    )
    TenantSettings.objects.create(tenant=tenant)

    limits = PLAN_LIMITS.get(subscription_plan, PLAN_LIMITS["starter"])
    tenant.config.max_branches = limits["max_branches"]
    tenant.config.max_customers = limits["max_customers"]
    tenant.config.max_trainers = limits["max_trainers"]
    tenant.config.save()

    return tenant
