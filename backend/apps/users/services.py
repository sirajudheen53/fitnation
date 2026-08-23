"""User business logic services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from apps.branches.models import Branch, BranchTrainerAssignment
from apps.customers.models import Customer
from apps.users.auth import AuthToken
from apps.users.models import User

if TYPE_CHECKING:
    from apps.tenants.models import Tenant


def create_user(
    tenant: Tenant,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    phone: str = "",
    password: str = "",
    branch_id: int | None = None,
    actor: User | None = None,  # noqa: ARG001
) -> User:
    """Create a new user within a tenant.

    Args:
        tenant: The tenant to associate with the user.
        email: User email (unique within tenant).
        first_name: First name.
        last_name: Last name.
        role: One of ``User.Role`` values.
        phone: Optional phone number.
        password: Optional raw password. If empty, an unusable password is set.
        branch_id: Optional branch to assign for trainer/customer roles.
        actor: The user creating the record, for audit purposes.

    Returns:
        The created ``User`` instance.
    """
    from apps.users.models import Trainer

    with transaction.atomic():
        user = User(
            tenant=tenant,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        if role == User.Role.TRAINER:
            Trainer.objects.create(user=user)
        elif role == User.Role.CUSTOMER:
            customer = Customer.objects.create(
                tenant=tenant,
                user=user,
                name=f"{first_name} {last_name}".strip(),
                email=email,
            )

        if branch_id and role in {User.Role.TRAINER, User.Role.CUSTOMER}:
            try:
                branch = Branch.objects.for_tenant(tenant).get(id=branch_id)
            except Branch.DoesNotExist:
                branch = None

            if branch:
                if role == User.Role.TRAINER:
                    BranchTrainerAssignment.objects.get_or_create(
                        branch=branch,
                        trainer=user.trainer_profile,
                        defaults={"is_active": True, "is_primary": True},
                    )
                elif role == User.Role.CUSTOMER:
                    customer.branch = branch
                    customer.save(update_fields=["branch"])

    return user


def create_owner_user(
    tenant: Tenant,
    email: str,
    password_hash: str,
    contact_name: str,
    phone: str = "",
) -> User:
    """Create the vendor owner user during onboarding.

    Args:
        tenant: The provisioned tenant.
        email: Owner email address.
        password_hash: Pre-hashed password from ``VendorRegistration``.
        contact_name: Full contact name split into first/last names.
        phone: Optional phone number.

    Returns:
        The created owner ``User`` instance.
    """
    parts = contact_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    user = User(
        tenant=tenant,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=User.Role.GYM_OWNER,
        is_owner=True,
    )
    user.password = password_hash
    user.save()
    return user


def issue_token(
    user: User,
    tenant: Tenant | None,
    device_type: str = "",
) -> AuthToken:
    """Issue a new active auth token for the user.

    Args:
        user: The authenticated user.
        tenant: The tenant context (``None`` for platform admins).
        device_type: Optional device type string.

    Returns:
        The created ``AuthToken`` instance.
    """
    token = AuthToken.objects.create(
        user=user,
        tenant=tenant,
        device_type=device_type or AuthToken.DeviceType.WEB,
    )
    return token


def deactivate_token(token_key: str) -> bool:
    """Deactivate a token by key.

    Args:
        token_key: The token key to deactivate.

    Returns:
        ``True`` if the token existed and was deactivated.
    """
    updated = AuthToken.objects.filter(key=token_key, is_active=True).update(
        is_active=False,
    )
    return bool(updated)


def get_user_permissions(user: User) -> list[str]:
    """Return the list of permission codes granted to the user's role.

    Args:
        user: The user whose permissions are queried.

    Returns:
        Sorted list of permission codes, or ``["*"]`` for wildcard roles.
    """
    from apps.permissions.permissions import RolePermission

    perms = RolePermission.ROLE_PERMISSION_MATRIX.get(user.role, set())
    if perms == "*":
        return ["*"]
    return sorted(perms)


def get_or_create_customer_by_phone(phone: str, tenant: Tenant) -> User:
    """Return an existing customer user by phone or create a new one.

    Used by the deterministic OTP verification stub. If a user does not exist, a new
    customer user is created with a generated email based on the phone number.

    Args:
        phone: Phone number used for OTP login.
        tenant: The tenant the customer belongs to.

    Returns:
        An existing or newly created customer ``User``.
    """
    email = f"{phone}@fitnation.local"
    user, _ = User.objects.get_or_create(
        tenant=tenant,
        email=email,
        defaults={
            "first_name": "Customer",
            "last_name": phone,
            "role": User.Role.CUSTOMER,
            "phone": phone,
        },
    )
    Customer.objects.get_or_create(
        user=user,
        defaults={
            "tenant": tenant,
            "name": f"Customer {phone}".strip(),
            "email": email,
        },
    )
    return user
