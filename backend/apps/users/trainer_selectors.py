"""Trainer read selectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, Q

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.tenants.models import Tenant
    from apps.users.models import Trainer, TrainerSchedule, TrainerCustomerAssignment


def trainer_list(
    tenant: "Tenant",
    is_active: bool | str | None = None,
    specialization: str | None = None,
    search: str | None = None,
) -> "QuerySet[Trainer]":
    """Return a tenant-scoped queryset of trainers with optional filters.

    Args:
        tenant: The tenant to filter by.
        is_active: Optional active flag filter (accepts bool or string).
        specialization: Optional specialization filter (case-insensitive).
        search: Optional name/email search term.

    Returns:
        Filtered queryset of Trainer instances.
    """
    from apps.users.models import Trainer

    qs = Trainer.objects.select_related("user").filter(user__tenant=tenant)

    if is_active is not None:
        if isinstance(is_active, str):
            is_active = is_active.lower() in ("true", "1", "yes")
        qs = qs.filter(is_active=is_active)
    if specialization:
        qs = qs.filter(specialization__icontains=specialization)
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search),
        )

    return qs.order_by("-created_at")


def trainer_get_by_id(tenant: "Tenant", trainer_id: int) -> "Trainer":
    """Return a tenant-scoped trainer by id.

    Args:
        tenant: The tenant the trainer must belong to.
        trainer_id: Primary key of the Trainer.

    Returns:
        The matching ``Trainer`` instance.

    Raises:
        Trainer.DoesNotExist: If the trainer is not found in the tenant.
    """
    from apps.users.models import Trainer

    return (
        Trainer.objects.select_related("user")
        .filter(user__tenant=tenant)
        .get(id=trainer_id)
    )


def trainer_schedule_list(
    tenant: "Tenant",
    trainer_id: int,
) -> "QuerySet[TrainerSchedule]":
    """Return schedules for a trainer within a tenant.

    Args:
        tenant: The tenant to scope by.
        trainer_id: The trainer's primary key.

    Returns:
        QuerySet of TrainerSchedule instances.
    """
    from apps.users.models import TrainerSchedule

    return TrainerSchedule.objects.filter(tenant=tenant, trainer_id=trainer_id)


def trainer_assignment_list(
    tenant: "Tenant",
    trainer_id: int | None = None,
    is_active: bool | None = None,
) -> "QuerySet[TrainerCustomerAssignment]":
    """Return customer assignments for a trainer within a tenant.

    Args:
        tenant: The tenant to scope by.
        trainer_id: Optional trainer filter.
        is_active: Optional active flag filter.

    Returns:
        QuerySet of TrainerCustomerAssignment instances.
    """
    from apps.users.models import TrainerCustomerAssignment

    qs = TrainerCustomerAssignment.objects.filter(tenant=tenant)
    if trainer_id is not None:
        qs = qs.filter(trainer_id=trainer_id)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs


def trainer_metrics(tenant: "Tenant", trainer_id: int) -> dict:
    """Return performance metrics for a single trainer.

    Args:
        tenant: The tenant to scope by.
        trainer_id: The trainer's primary key.

    Returns:
        Dict with active_clients, rating, max_clients, utilization, total_assignments.
    """
    from apps.users.models import Trainer, TrainerCustomerAssignment

    trainer = trainer_get_by_id(tenant, trainer_id)

    active = TrainerCustomerAssignment.objects.filter(
        tenant=tenant,
        trainer=trainer,
        is_active=True,
    ).count()

    total = TrainerCustomerAssignment.objects.filter(
        tenant=tenant,
        trainer=trainer,
    ).count()

    max_clients = trainer.max_clients or 1
    utilization = round((active / max_clients) * 100, 2) if max_clients else 0.0

    return {
        "trainer_id": trainer.id,
        "active_clients": active,
        "rating": float(trainer.rating),
        "max_clients": trainer.max_clients,
        "utilization": utilization,
        "total_assignments": total,
    }