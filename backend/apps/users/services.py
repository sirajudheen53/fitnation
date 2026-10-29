"""User business logic services."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.branches.models import Branch, BranchTrainerAssignment
from apps.customers.models import (
    DELETED_USER_LABEL,
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)
from apps.notifications.models import DeviceToken
from apps.tenants.gym_codes import canonical_gym_code
from apps.tenants.models import Tenant
from apps.users.auth import AuthToken
from apps.users.models import EmailVerificationToken, OtpCode, User
from apps.users.phone import phone_lookup_candidates

logger = logging.getLogger(__name__)

# Synthetic OTP identities live under this domain. Both the legacy
# ``{phone}@fitnation.local`` and the tenant-scoped
# ``{phone}.{tenant_uuid}@fitnation.local`` schemes share the suffix; identity
# checks should match on the domain, not the exact format (FBOS-011 §3.5).
SYNTHETIC_EMAIL_DOMAIN = "@fitnation.local"

# Replacement domain for deleted identities — deliberately NOT the synthetic
# ``@fitnation.local`` suffix, so a deleted row can never be mistaken for a
# live phone-keyed OTP identity (identity checks match on that suffix).
DELETED_EMAIL_DOMAIN = "@deleted.invalid"


def deleted_account_email() -> str:
    """A neutral, unique replacement for a deleted identity's email.

    The uuid is generated at deletion time and derived from nothing, so the
    address carries no personal data and cannot be linked back to the
    account holder; uniqueness keeps the globally-unique ``User.email``
    constraint intact.
    """
    return f"deleted-{uuid.uuid4().hex}{DELETED_EMAIL_DOMAIN}"


def delete_customer_account(user: User, tenant: Tenant) -> Customer | None:
    """Delete the caller's own account the GDPR/Google-Play way (§8 task B8).

    Google Play requires a working in-app account-deletion path for an app
    that stores personal data — this one stores health data — so the
    customer app calls ``POST /users/auth/delete-account/`` with its token;
    the endpoint acts on ``request.user`` only and never accepts a target
    user.

    What happens to the data:

    * **Anonymised in place** (rows stay for referential integrity, personal
      values scrubbed to neutral): the ``User`` row (name → ``Deleted
      Member``, email → a random ``deleted-<uuid>@deleted.invalid``, phone →
      empty, ``is_email_verified`` off, ``is_active`` off so it can never
      log in again) and the linked ``Customer`` profile (name → the issue
      #81 "Deleted user" marker + ``deleted_at`` set, email, phone, date of
      birth, emergency contacts, address, notes and profile photo scrubbed;
      gender reset to "prefer not to say"; ``is_active`` off and ``status``
      set to ``inactive``). Business records that reference the member
      therefore survive but no longer point at a natural person.
    * **Purged outright** — health data and session/identity plumbing with
      no statutory-records claim: the ``HealthProfile`` row, its
      ``BodyMeasurement``/``FitnessGoal``/``ProgressPhoto`` rows, every
      ``OtpCode`` issued for the user's phone within the tenant, the user's
      ``DeviceToken`` push registrations within the tenant and any
      ``EmailVerificationToken`` rows.
    * **Revoked immediately** — all ``AuthToken`` rows for the user
      (``is_active=False``, the same pattern ``MembershipViewSet.cancel``
      uses): every device is logged out in the same atomic transaction.
    * **Retained but non-identifying** — memberships, payments, invoices,
      attendance, trainer assignments and access logs (statutory/financial
      retention); they keep pointing at the anonymised customer row.
    * **Never touched** — rows outside ``tenant``: OTP codes and push
      bindings are per-gym and the same human may be a live member at
      another gym (ADR-002 rule 2).

    Args:
        user: The customer account to delete (the caller's own).
        tenant: The tenant whose member data the caller controls.

    Returns:
        The scrubbed, deactivated ``Customer`` row, or ``None`` when the
        user had no customer profile (an anonymous identity is scrubbed all
        the same).
    """
    phone = user.phone
    customer = Customer.objects.filter(tenant=tenant, user=user).first()
    tenant_scope = Q(tenant=tenant) if tenant is not None else Q(pk__isnull=True)

    with transaction.atomic():
        if phone:
            OtpCode.objects.filter(tenant_scope, phone=phone).delete()
        token_scope = Q(user=user)
        if customer is not None:
            token_scope |= Q(customer=customer)
        DeviceToken.objects.filter(tenant_scope, token_scope).delete()

        if customer is not None:
            HealthProfile.objects.filter(tenant_scope, customer=customer).delete()
            BodyMeasurement.objects.filter(tenant_scope, customer=customer).delete()
            FitnessGoal.objects.filter(tenant_scope, customer=customer).delete()
            ProgressPhoto.objects.filter(tenant_scope, customer=customer).delete()
            # Issue #81: the same soft-delete marker + display label the ERP
            # delete uses, so every surface renders the member identically —
            # whether they were removed by the gym or deleted their own
            # account. (Previously "Deleted member #pk"; the label is what
            # every ``customer.name`` reference shows now.)
            customer.deleted_at = timezone.now()
            customer.name = DELETED_USER_LABEL
            customer.email = None
            customer.phone = ""
            customer.date_of_birth = None
            customer.gender = Customer.Gender.PREFER_NOT_TO_SAY
            customer.emergency_contact_name = None
            customer.emergency_contact_phone = None
            customer.address_street = ""
            customer.address_city = ""
            customer.address_state = ""
            customer.address_postal_code = ""
            customer.profile_photo = None
            customer.notes = ""
            customer.status = Customer.Status.INACTIVE
            customer.is_active = False
            customer.save()

        EmailVerificationToken.objects.filter(user=user).delete()
        AuthToken.objects.filter(user=user, is_active=True).update(is_active=False)

        user.first_name = "Deleted"
        user.last_name = "Member"
        user.email = deleted_account_email()
        user.phone = ""
        user.is_email_verified = False
        user.is_active = False
        user.save(
            update_fields=[
                "first_name",
                "last_name",
                "email",
                "phone",
                "is_email_verified",
                "is_active",
            ]
        )
    return customer


class AutoProvisionLimitReached(Exception):
    """The tenant's daily cap on OTP-auto-created identities was exceeded.

    Surfaced as a generic 429 — the member already proved phone possession at
    this point, so the message reveals nothing a verified caller didn't know.
    """

    def __init__(self) -> None:
        super().__init__("Daily account creation limit reached for this gym.")
        self.detail = {"detail": "Too many requests. Try again later."}
        self.status_code = 429


def create_user(
    tenant: Tenant,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    phone: str = "",
    password: str = "",
    branch_id: int | None = None,
    actor: User | None = None,
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
    expires_at: datetime | None = None,
) -> AuthToken:
    """Issue a new active auth token for the user.

    Args:
        user: The authenticated user.
        tenant: The tenant context (``None`` for platform admins).
        device_type: Optional device type string.
        expires_at: Optional absolute expiry (``None`` = no expiry). Short
            expiries are used for admin impersonation sessions.

    Returns:
        The created ``AuthToken`` instance.
    """
    token = AuthToken.objects.create(
        user=user,
        tenant=tenant,
        device_type=device_type or AuthToken.DeviceType.WEB,
        expires_at=expires_at,
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


APP_ACCESS_PERMISSION = "app.access"


def get_effective_permissions(user: User, tenant: Tenant | None) -> list[str]:
    """Role permissions plus entitlement-derived codes (customers only).

    RBAC stays static (FBOS-009): the customer role's matrix entry is the base
    set for every customer. Entitlement (ADR-003) layers ``app.access`` on top
    — appended only while the member's app-access state is ``active`` or
    ``grace``. Non-customer roles resolve exactly as
    :func:`get_user_permissions` (wildcard roles still ``["*"]``); the
    read-only grace case is communicated by the separate ``entitlement``
    payload (:func:`build_entitlement_payload`), not by a permission code.

    Args:
        user: The authenticated user.
        tenant: The tenant context the entitlement is evaluated in.

    Returns:
        Sorted list of permission codes, or ``["*"]`` for wildcard roles.
    """
    base = get_user_permissions(user)
    if base == ["*"] or user.role != User.Role.CUSTOMER or tenant is None:
        return base
    from apps.memberships.selectors import get_app_entitlement

    customer = Customer.objects.filter(tenant=tenant, user=user).only("id").first()
    entitlement = get_app_entitlement(customer, tenant=tenant)
    if entitlement.entitled:
        return sorted({*base, APP_ACCESS_PERMISSION})
    return base


def build_entitlement_payload(user: User, tenant: Tenant | None) -> dict | None:
    """Build the mobile-facing ``entitlement`` object for auth responses.

    Shape (FBOS-011 §2.3): ``{"status", "read_only", "plan_name", "end_date",
    "grace_end_date", "gym": {"uuid", "name"}}`` — a status string plus a
    read-only flag; the app derives everything else (gate copy, banners) from
    these. ``None`` for non-customer roles (staff have no member entitlement).

    Args:
        user: The authenticated user.
        tenant: The tenant context (anchored gym in the payload).

    Returns:
        The entitlement dict for customers, else ``None``.
    """
    if user.role != User.Role.CUSTOMER or tenant is None:
        return None
    from apps.memberships.selectors import get_app_entitlement

    customer = Customer.objects.filter(tenant=tenant, user=user).only("id").first()
    entitlement = get_app_entitlement(customer, tenant=tenant)
    payload = entitlement.as_payload()
    payload["gym"] = {"uuid": str(tenant.uuid), "name": tenant.name}
    return payload


def synthetic_otp_email(phone: str, tenant: Tenant) -> str:
    """The tenant-scoped synthetic email for a phone-keyed OTP identity.

    ``User.email`` is globally unique while the phone is only unique per
    tenant — the same human at two gyms must get two accounts (ADR-002 rule
    2), so the synthetic address carries the tenant uuid. Legacy
    ``{phone}@fitnation.local`` rows are NOT migrated: phone-match converges
    before the email ever matters, and identity checks match on the
    ``@fitnation.local`` domain suffix rather than an exact format.

    Args:
        phone: The member's phone number.
        tenant: The tenant (gym) the identity belongs to.

    Returns:
        A ``{phone}.{tenant_uuid}@fitnation.local`` address.
    """
    return f"{phone}.{tenant.uuid}{SYNTHETIC_EMAIL_DOMAIN}"


class TenantResolutionError(Exception):
    """An OTP tenant-resolution error (explicit anchors only, FBOS-011 §3)."""

    def __init__(self, detail: dict, status_code: int = 400):
        super().__init__(str(detail))
        self.detail = detail
        self.status_code = status_code


def _throttle_lookup(phone: str, ip: str | None) -> None:
    """Rate-limit cross-tenant phone lookups (per phone + IP, 10 per 10 min).

    Best-effort: a cache failure skips the throttle (fail-open) — the hard
    daily caps in the OTP issue path remain the enforcement layer.
    """
    from django.core.cache import cache

    try:
        key = f"otp-anchor:{phone}:{ip or 'noip'}"
        count = (cache.get(key) or 0) + 1
        cache.set(key, count, timeout=600)
        if count > 10:
            raise TenantResolutionError({"detail": "Too many requests. Try again later."}, status_code=429)
    except Exception:  # noqa: BLE001 — throttle best-effort — cache loss must not block
        logger.warning("OTP anchor throttle skipped (cache unavailable)")


def resolve_tenant_for_otp(phone: str, gym_anchor: str | None, ip: str | None = None):
    """Resolve the tenant for an OTP flow — explicit anchors ONLY (FBOS-011 §3).

    Ladder:
    1. Device-bound gym anchor — tenant uuid (deep-link/install capture) or,
       since #87, the gym's short signup code (the zero-match recovery path:
       a first-time member types the code their gym shared, canonicalized
       exactly like ``GET /tenants/lookup/``) → explicit, validated.
    2. Rate-limited cross-tenant phone lookup: exactly one customer user →
       auto-pin; several → a minimal disambiguation list (tenant uuid +
       display name only, throttled, non-enumerating shape); zero matches →
       a generic non-enumerating error.

    Returns:
        (tenant, None) on resolution, or (None, disambiguation_payload).

    Raises:
        TenantResolutionError: on anchor failures (never a fallback).
    """
    if gym_anchor:
        _throttle_lookup(phone, ip)
        # UUID branch: only when the anchor parses as one — Django's UUIDField
        # raises ValidationError (not ValueError) on hand-typed strings, and
        # the gym-code branch below must get its chance (#87).
        try:
            anchor_uuid = uuid.UUID(str(gym_anchor))
        except ValueError:
            anchor_uuid = None
        if anchor_uuid is not None:
            try:
                return Tenant.objects.get(uuid=anchor_uuid), None
            except Tenant.DoesNotExist:
                pass  # not a known uuid — fall through to the gym-code anchor (#87)
        # Hand-typed signup code: same canonicalization as the lookup endpoint,
        # so " px3-ctjy " anchors like PX3CTJY. A uuid string can never match a
        # 7-char code, so this never widens the uuid branch above.
        code = canonical_gym_code(gym_anchor)
        if code:
            tenant = Tenant.objects.filter(gym_code=code).first()
            if tenant is not None:
                return tenant, None
        raise TenantResolutionError({"gym": "Unknown gym."}, status_code=400) from None

    _throttle_lookup(phone, ip)
    # phone__in over every storage format (#88): Firebase hands the claim in
    # E.164 while rows may still sit under the raw typed form until the data
    # migration (users 0008) lands — both must resolve.
    users = list(
        User.objects.filter(role=User.Role.CUSTOMER, phone__in=phone_lookup_candidates(phone)).select_related("tenant")
    )
    tenants = {u.tenant for u in users if u.tenant is not None}
    if len(tenants) == 1:
        return next(iter(tenants)), None
    if len(tenants) > 1:
        return None, {
            "action": "select_gym",
            "gyms": [{"tenant": str(t.uuid), "name": t.name} for t in sorted(tenants, key=lambda x: x.name.lower())],
        }
    # Zero matches — generic, non-enumerating; never reveals registration state.
    raise TenantResolutionError({"detail": "Specify your gym to continue."}, status_code=400)


def _check_auto_create_cap(tenant: Tenant) -> None:
    """Enforce the per-tenant daily cap on OTP-auto-created identities.

    Auto-create exists for invited walk-ins, not for farming rows
    (FBOS-011 §3.1). Cache counter, fail-open like the anchor throttle — the
    DB-enforced OTP daily caps remain the hard layer.

    Args:
        tenant: The tenant the new identity would be created in.

    Raises:
        AutoProvisionLimitReached: When the cap
            (``APP_AUTOCREATE_DAILY_LIMIT``, default 50) is exhausted.
    """
    from django.conf import settings as dj_settings
    from django.core.cache import cache

    cap = int(getattr(dj_settings, "APP_AUTOCREATE_DAILY_LIMIT", 50))
    # Key by UUID, not pk: pks are recyclable (reused after a rollback/reset),
    # so a stale counter for a dead tenant would silently cap a new one.
    # Accepted v1 limitation: the daily cap is per cache instance —
    # config/settings/cloudrun.py uses per-instance LocMem, so limits are not
    # shared across GCP instances; a Redis shared cache can raise this later.
    key = f"app-autocreate:{tenant.uuid}:{timezone.localdate().isoformat()}"
    try:
        count = cache.get(key) or 0
        if count >= cap:
            raise AutoProvisionLimitReached()
        cache.set(key, count + 1, timeout=90000)
    except AutoProvisionLimitReached:
        raise
    except Exception:  # noqa: BLE001 - cache failure must not block logins
        logger.warning("Auto-create cap check skipped (cache unavailable)")


def get_or_create_customer_by_phone(phone: str, tenant: Tenant) -> User:
    """Return an existing customer user by phone or create a new one.

    Used by OTP verification (FBOS-011 §3): auto-provisioning STAYS — killing
    it would let an attacker distinguish invited phones from unknown ones
    before possessing them — but a freshly created identity carries no
    membership, so it resolves to entitlement ``none`` (no ``app.access``).
    The synthetic email is tenant-scoped (:func:`synthetic_otp_email`) so the
    same phone at two gyms no longer IntegrityErrors on the second gym.

    Args:
        phone: Phone number used for OTP login.
        tenant: The tenant the customer belongs to.

    Returns:
        An existing or newly created customer ``User``.

    Raises:
        AutoProvisionLimitReached: When the tenant's daily auto-create cap is
            hit (generic non-enumerating 429 at the view layer).
    """
    # ADR-002 rule 2: reuse an existing owner-created customer user in the
    # tenant before provisioning a synthetic phone-keyed identity. Tolerant
    # candidates (#88): the candidate may arrive E.164 from Firebase while
    # the stored row still carries the raw typed form.
    existing = (
        User.objects.filter(
            tenant=tenant,
            phone__in=phone_lookup_candidates(phone),
            role=User.Role.CUSTOMER,
        )
        .order_by("id")
        .first()
    )
    if existing is not None:
        Customer.objects.get_or_create(
            user=existing,
            defaults={
                "tenant": tenant,
                "name": existing.get_full_name() or existing.email,
                "email": existing.email,
            },
        )
        return existing

    _check_auto_create_cap(tenant)

    email = synthetic_otp_email(phone, tenant)
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
            "email": None,
        },
    )
    return user
