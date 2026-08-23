"""Vendor onboarding business logic services."""

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from apps.branches.models import Branch
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token
from apps.vendors.emails import send_verification_email, send_welcome_email
from apps.vendors.models import SubscriptionPlan, VendorRegistration


def create_vendor_registration(
    business_name: str,
    contact_name: str,
    email: str,
    phone: str,
    password: str,
) -> VendorRegistration:
    """Create a new vendor registration record.

    Args:
        business_name: Name of the gym business.
        contact_name: Name of the primary contact.
        email: Contact email used for verification.
        phone: Optional phone number.
        password: Raw password to hash and store.

    Returns:
        The created ``VendorRegistration`` instance.
    """
    return VendorRegistration.objects.create(
        email=email,
        business_name=business_name,
        contact_name=contact_name,
        contact_phone=phone,
        password_hash=make_password(password),
    )


def verify_registration_email(token: str) -> VendorRegistration:
    """Verify a vendor registration email via token.

    Args:
        token: The email verification token.

    Returns:
        The updated ``VendorRegistration`` instance.

    Raises:
        VendorRegistration.DoesNotExist: If the token is invalid or already verified.
    """
    registration = VendorRegistration.objects.get(
        email_verification_token=token,
        current_step=VendorRegistration.Step.STARTED,
    )
    registration.email_verified_at = timezone.now()
    registration.current_step = VendorRegistration.Step.EMAIL_VERIFIED
    registration.save()
    return registration


def resend_verification_email(email: str) -> VendorRegistration:
    """Regenerate and "re-send" the verification email.

    Args:
        email: Email address of the registration.

    Returns:
        The updated ``VendorRegistration`` instance.

    Raises:
        VendorRegistration.DoesNotExist: If no matching registration exists.
    """
    registration = VendorRegistration.objects.get(email=email)
    registration.email_verification_token = uuid.uuid4()
    registration.save()
    send_verification_email(registration)
    return registration


def select_plan_and_provision(registration_id: int, plan_code: str) -> dict:
    """Select a plan, provision the tenant, and create the owner user.

    Args:
        registration_id: Primary key of the ``VendorRegistration``.
        plan_code: One of the ``SubscriptionPlan`` codes.

    Returns:
        A dictionary containing the tenant, auth token, and next step.

    Raises:
        ValidationError: If the registration step or plan is invalid.
    """
    with transaction.atomic():
        registration = VendorRegistration.objects.select_for_update().get(
            id=registration_id,
            current_step=VendorRegistration.Step.EMAIL_VERIFIED,
        )
        plan = SubscriptionPlan.objects.get(code=plan_code, is_active=True)

        registration.selected_plan = plan.code
        registration.current_step = VendorRegistration.Step.PLAN_SELECTED
        registration.save()

        tenant = provision_tenant(
            name=registration.business_name,
            contact_email=registration.email,
            subscription_plan=plan.code,
        )

        owner = create_owner_user(
            tenant=tenant,
            email=registration.email,
            password_hash=registration.password_hash,
            contact_name=registration.contact_name,
            phone=registration.contact_phone,
        )

        token = issue_token(owner, tenant)

        registration.current_step = VendorRegistration.Step.PROVISIONED
        registration.provisioned_tenant_id = tenant.id
        registration.save()

        send_welcome_email(registration, tenant)

    return {
        "tenant": tenant,
        "owner": owner,
        "token": token,
        "next_step": "onboarding_wizard",
    }


def complete_onboarding(
    user: User,
    business_type: str,
    branches_count: int,
    primary_branch_name: str,
    primary_branch_address: str,
    primary_branch_phone: str = "",
) -> dict:
    """Complete vendor onboarding by creating the default branch.

    Args:
        user: The authenticated owner user completing onboarding.
        business_type: Type of fitness business.
        branches_count: Number of branches the vendor intends to operate.
        primary_branch_name: Name of the first branch.
        primary_branch_address: Address of the first branch.
        primary_branch_phone: Phone number of the first branch.

    Returns:
        A dictionary with the created branch and redirect target.
    """
    tenant = user.tenant
    if tenant is None:
        raise ValueError("Onboarding user must belong to a tenant")

    branch = Branch.objects.create(
        tenant=tenant,
        name=primary_branch_name,
        address_line1=primary_branch_address,
        phone=primary_branch_phone,
        is_headquarters=True,
        metadata={"business_type": business_type, "branches_count": branches_count},
    )

    VendorRegistration.objects.filter(
        provisioned_tenant_id=tenant.id,
        current_step=VendorRegistration.Step.PROVISIONED,
    ).update(current_step=VendorRegistration.Step.ONBOARDED)

    return {
        "branch": branch,
        "message": "Onboarding completed",
        "redirect_to": "/dashboard",
    }


import uuid  # noqa: E402
