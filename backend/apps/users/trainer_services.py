"""Trainer business logic services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from apps.tenants.models import Tenant
    from apps.users.models import Trainer, TrainerCustomerAssignment, TrainerSchedule


def create_trainer(
    tenant: "Tenant",
    email: str,
    first_name: str,
    last_name: str,
    phone: str = "",
    password: str = "",
    specialization: str = "",
    bio: str = "",
    certifications: list | None = None,
    experience_years: int = 0,
    max_clients: int = 50,
    profile_photo: str = "",
    actor: object | None = None,  # noqa: ARG001
) -> "Trainer":
    """Create a new user with trainer role and trainer profile.

    Args:
        tenant: The tenant to associate with the user.
        email: User email (unique platform-wide).
        first_name: First name.
        last_name: Last name.
        phone: Optional phone number.
        password: Optional raw password. If empty, unusable password is set.
        specialization: Trainer specialization.
        bio: Trainer bio.
        certifications: List of certification dicts.
        experience_years: Years of experience.
        max_clients: Max simultaneous clients.
        profile_photo: URL to profile photo.
        actor: The user creating the record, for audit.

    Returns:
        The created ``Trainer`` instance.
    """
    from apps.users.models import Trainer, User

    with transaction.atomic():
        user = User(
            tenant=tenant,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=User.Role.TRAINER,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        trainer = Trainer.objects.create(
            user=user,
            specialization=specialization,
            bio=bio,
            certifications=certifications or [],
            experience_years=experience_years,
            max_clients=max_clients,
            profile_photo=profile_photo,
        )

    return trainer


def update_trainer(
    trainer: "Trainer",
    **fields: object,
) -> "Trainer":
    """Update trainer profile fields.

    Args:
        trainer: The Trainer instance to update.
        **fields: Fields to update.

    Returns:
        The updated ``Trainer`` instance.
    """
    for key, value in fields.items():
        if hasattr(trainer, key):
            setattr(trainer, key, value)
    trainer.save()
    return trainer


def create_schedule(
    tenant: "Tenant",
    trainer: "Trainer",
    day_of_week: str,
    start_time: str,
    end_time: str,
    is_available: bool = True,
) -> "TrainerSchedule":
    """Create a schedule entry for a trainer.

    Args:
        tenant: The tenant to scope by.
        trainer: The Trainer instance.
        day_of_week: Day choice value.
        start_time: Start time string (HH:MM).
        end_time: End time string (HH:MM).
        is_available: Whether the slot is available.

    Returns:
        The created ``TrainerSchedule`` instance.
    """
    from apps.users.models import TrainerSchedule

    return TrainerSchedule.objects.create(
        tenant=tenant,
        trainer=trainer,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        is_available=is_available,
    )


def update_schedule(
    schedule: "TrainerSchedule",
    **fields: object,
) -> "TrainerSchedule":
    """Update a schedule entry.

    Args:
        schedule: The TrainerSchedule instance.
        **fields: Fields to update.

    Returns:
        The updated ``TrainerSchedule`` instance.
    """
    for key, value in fields.items():
        if hasattr(schedule, key):
            setattr(schedule, key, value)
    schedule.save()
    return schedule


def assign_customer_to_trainer(
    tenant: "Tenant",
    trainer: "Trainer",
    customer_id: int,
) -> "TrainerCustomerAssignment":
    """Assign a customer to a trainer (create or reactivate).

    Args:
        tenant: The tenant to scope by.
        trainer: The Trainer instance.
        customer_id: The Customer primary key.

    Returns:
        The ``TrainerCustomerAssignment`` instance.
    """
    from apps.customers.models import Customer
    from apps.users.models import TrainerCustomerAssignment

    customer = Customer.objects.get(id=customer_id, tenant=tenant)

    assignment, created = TrainerCustomerAssignment.objects.get_or_create(
        tenant=tenant,
        trainer=trainer,
        customer=customer,
        defaults={"is_active": True},
    )
    if not created and not assignment.is_active:
        assignment.is_active = True
        assignment.unassigned_at = None
        assignment.save(update_fields=["is_active", "unassigned_at", "updated_at"])

    return assignment


def unassign_customer_from_trainer(
    assignment: "TrainerCustomerAssignment",
) -> "TrainerCustomerAssignment":
    """Mark a trainer-customer assignment as inactive.

    Args:
        assignment: The TrainerCustomerAssignment instance.

    Returns:
        The updated ``TrainerCustomerAssignment`` instance.
    """
    assignment.is_active = False
    assignment.unassigned_at = timezone.now()
    assignment.save(update_fields=["is_active", "unassigned_at", "updated_at"])
    return assignment
