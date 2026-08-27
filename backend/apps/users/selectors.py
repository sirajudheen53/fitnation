"""User read selectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.tenants.models import Tenant
    from apps.users.models import User


def user_list(
    tenant: Tenant,
    role: str | None = None,
    branch_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> QuerySet[User]:
    """Return a tenant-scoped queryset of users with optional filters.

    Args:
        tenant: The tenant to filter by.
        role: Optional role code filter.
        branch_id: Optional branch filter (via trainer/customer profiles).
        is_active: Optional active flag filter.
        search: Optional name/email search term.

    Returns:
        Filtered queryset of users.
    """
    from apps.users.models import User

    qs = User.objects.for_tenant(tenant)

    if role:
        qs = qs.filter(role=role)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        qs = qs.filter(
            Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search),
        )

    if branch_id is not None:
        qs = qs.filter(
            Q(customer_profile__branch_id=branch_id) | Q(trainer_profile__branch_assignments__branch_id=branch_id),
        ).distinct()

    return qs.order_by("-created_at")


def user_get_by_id(tenant: Tenant, user_id: int) -> User:
    """Return a tenant-scoped user by id.

    Args:
        tenant: The tenant the user must belong to.
        user_id: Primary key of the user.

    Returns:
        The matching ``User`` instance.

    Raises:
        User.DoesNotExist: If the user is not found in the tenant.
    """
    from apps.users.models import User

    return User.objects.for_tenant(tenant).get(id=user_id)
