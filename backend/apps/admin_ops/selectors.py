"""Admin ops selectors — cross-tenant reads (platform admin only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, IntegerField, OuterRef, QuerySet, Subquery
from django.db.models.functions import Coalesce

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.models import Tenant

if TYPE_CHECKING:
    pass


def list_tenants() -> QuerySet[Tenant]:
    """Return all tenants annotated with member and branch counts.

    ``TenantModelMixin`` disables reverse relations (``related_name="+"``),
    so counts use correlated subqueries instead of ``Count`` annotations.

    Returns:
        Tenant queryset ordered newest-first, annotated with
        ``member_count`` and ``branch_count``.
    """
    member_sq = (
        Customer.objects.filter(tenant_id=OuterRef("pk"))
        .values("tenant_id")
        .annotate(c=Count("id"))
        .values("c")[:1]
    )
    branch_sq = (
        Branch.objects.filter(tenant_id=OuterRef("pk"))
        .values("tenant_id")
        .annotate(c=Count("id"))
        .values("c")[:1]
    )
    return Tenant.objects.annotate(
        member_count=Coalesce(Subquery(member_sq, output_field=IntegerField()), 0),
        branch_count=Coalesce(Subquery(branch_sq, output_field=IntegerField()), 0),
    ).order_by("-created_at")
