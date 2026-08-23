"""Tenant read selectors."""

from apps.tenants.models import Tenant


def tenant_get_by_id(tenant_id: int) -> Tenant:
    """Return a tenant by primary key.

    Args:
        tenant_id: Primary key of the tenant.

    Returns:
        The matching ``Tenant`` instance.

    Raises:
        Tenant.DoesNotExist: If no tenant with the given id exists.
    """
    return Tenant.objects.get(id=tenant_id)
