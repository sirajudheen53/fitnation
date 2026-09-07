"""Tenants A/B regression seed — port of ``backend/seed_qa.py``.

FitGym A (professional) and FitGym B (starter) with owner + customer users,
customer profiles, branches, plans, memberships, payments, fitness goal and
body measurement — used for cross-tenant isolation regression (BUG-2026-08-27-01)
and customer self-access regression (BUG-2026-08-27-02).

Fix vs original: provisioned tenants are forced to ACTIVE (provision_tenant
defaults to TRIAL, which LoginView rejects).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.branches.models import Branch
from apps.customers.models import BodyMeasurement, Customer, FitnessGoal
from apps.memberships.models import Membership, MembershipPlan
from apps.payments.models import Payment
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user

from .common import PASSWORDS, ensure_active, ensure_password, ensure_user


def _backfill_paid_at(payment: Payment, fallback_date: date) -> None:
    """Older seeds created completed payments without paid_at.

    Revenue dashboards filter ``paid_at__isnull=False``, so NULL rows are
    invisible. Backfill with a date derived from the linked membership so the
    revenue series includes them (idempotent: skips already-dated rows).
    """
    if payment.paid_at is not None:
        return
    start = payment.membership.start_date if payment.membership else fallback_date
    payment.paid_at = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    payment.save(update_fields=["paid_at"])


def _ensure_tenant(name: str, contact_email: str, plan: str) -> Tenant:
    tenant = Tenant.objects.filter(name=name).first()
    if tenant is None:
        tenant = provision_tenant(name=name, contact_email=contact_email, subscription_plan=plan)
    ensure_active(tenant)
    return tenant


def _ensure_owner(tenant: Tenant, email: str, contact_name: str, phone: str,
                  reset_passwords: bool = True) -> User:
    owner = User.objects.filter(email=email).first()
    if owner is None:
        owner = create_owner_user(
            tenant=tenant,
            email=email,
            contact_name=contact_name,
            phone=phone,
            password_hash=make_password(PASSWORDS["tenant_ab"]),
        )
    if not owner.is_email_verified:
        owner.is_email_verified = True
        owner.save(update_fields=["is_email_verified"])
    ensure_password(owner, PASSWORDS["tenant_ab"], reset=reset_passwords)
    return owner


def _ensure_customer_user(tenant: Tenant, email: str, first: str, last: str, phone: str) -> User:
    return ensure_user(
        email=email,
        first_name=first,
        last_name=last,
        role=User.Role.CUSTOMER,
        password=PASSWORDS["tenant_ab"],
        tenant=tenant,
        phone=phone,
        is_staff=False,
    )


def seed(reset_passwords: bool = True, echo=print) -> dict:
    """Seed FitGym A and FitGym B with regression data.

    Args:
        reset_passwords: Align existing account passwords with documented values.
        echo: Progress sink.

    Returns:
        Dict with the seeded tenants and users.
    """
    # ── Tenant A: FitGym A ────────────────────────────────────────────────
    tenant_a = _ensure_tenant("FitGym A", "admin@fitgyma.qa", "professional")
    owner_a = _ensure_owner(tenant_a, "owner_a@fitgyma.qa", "Rahul Sharma",
                            "+919876543210", reset_passwords)
    customer_a = _ensure_customer_user(
        tenant_a, "customer_a@fitgyma.qa", "Priya", "Verma", "+919876543211"
    )

    customer_profile_a = Customer.objects.filter(user=customer_a).first()
    if customer_profile_a is None:
        customer_profile_a = Customer.objects.create(
            tenant=tenant_a,
            user=customer_a,
            date_of_birth=date(1995, 3, 15),
            gender="female",
            emergency_contact_name="Amit Verma",
            emergency_contact_phone="+919876543213",
            address_city="Bangalore",
            status="active",
        )

    branch_a = Branch.objects.filter(tenant=tenant_a, name="FitGym A — Main Branch").first()
    if branch_a is None:
        branch_a = Branch.objects.create(
            tenant=tenant_a,
            name="FitGym A — Main Branch",
            address_line1="123 MG Road",
            address_line2="Bangalore",
            phone="+919876543212",
            email="main@fitgyma.qa",
            is_active=True,
        )

    plan_a = MembershipPlan.objects.filter(tenant=tenant_a, name="Premium Annual").first()
    if plan_a is None:
        plan_a = MembershipPlan.objects.create(
            tenant=tenant_a,
            name="Premium Annual",
            description="Full gym access + personal training",
            duration_days=365,
            price=15000.0,
            is_active=True,
        )

    membership_a = Membership.objects.filter(customer=customer_profile_a, plan=plan_a).first()
    if membership_a is None:
        membership_a = Membership.objects.create(
            customer=customer_profile_a,
            plan=plan_a,
            tenant=tenant_a,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Membership.Status.ACTIVE,
            auto_renew=False,
        )

    payment_a = Payment.objects.filter(customer=customer_profile_a).first()
    if payment_a is None:
        payment_a = Payment.objects.create(
            tenant=tenant_a,
            customer=customer_profile_a,
            membership=membership_a,
            amount=15000.0,
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.COMPLETED,
            transaction_id=f"txn_fitgyma_{uuid.uuid4().hex[:8]}",
            paid_at=timezone.make_aware(datetime(2026, 1, 1, 10, 0)),
        )
    _backfill_paid_at(payment_a, fallback_date=date(2026, 1, 1))

    goal_a = FitnessGoal.objects.filter(customer=customer_profile_a, is_active=True).first()
    if goal_a is None:
        FitnessGoal.objects.create(
            tenant=tenant_a,
            customer=customer_profile_a,
            goal_type=FitnessGoal.GoalType.LOSE_WEIGHT,
            target_value=60.0,
            current_value=75.0,
            target_date=date(2026, 12, 31),
            notes="Lose 15kg by year end",
            is_active=True,
        )

    if not BodyMeasurement.objects.filter(customer=customer_profile_a).exists():
        BodyMeasurement.objects.create(
            tenant=tenant_a,
            customer=customer_profile_a,
            date_logged=datetime.now().date(),
            weight_kg=75.0,
            height_cm=165.0,
            body_fat_percentage=28.0,
        )
    echo(f"  FitGym A: {owner_a.email}, {customer_a.email} (+membership/payment/goal)")

    # ── Tenant B: FitGym B ────────────────────────────────────────────────
    tenant_b = _ensure_tenant("FitGym B", "admin@fitgymb.qa", "starter")
    owner_b = _ensure_owner(tenant_b, "owner_b@fitgymb.qa", "Suresh Patel",
                            "+919876543220", reset_passwords)
    customer_b = _ensure_customer_user(
        tenant_b, "customer_b@fitgymb.qa", "Anita", "Desai", "+919876543221"
    )

    customer_profile_b = Customer.objects.filter(user=customer_b).first()
    if customer_profile_b is None:
        customer_profile_b = Customer.objects.create(
            tenant=tenant_b,
            user=customer_b,
            date_of_birth=date(1990, 7, 20),
            gender="female",
            emergency_contact_name="Ravi Desai",
            emergency_contact_phone="+919876543222",
            address_city="Mumbai",
            status="active",
        )

    branch_b = Branch.objects.filter(tenant=tenant_b, name="FitGym B — Branch").first()
    if branch_b is None:
        Branch.objects.create(
            tenant=tenant_b,
            name="FitGym B — Branch",
            address_line1="45 Linking Road",
            address_line2="Mumbai",
            phone="+919876543223",
            email="main@fitgymb.qa",
            is_active=True,
        )

    plan_b = MembershipPlan.objects.filter(tenant=tenant_b, name="Basic Monthly").first()
    if plan_b is None:
        plan_b = MembershipPlan.objects.create(
            tenant=tenant_b,
            name="Basic Monthly",
            description="Gym access only",
            duration_days=30,
            price=2000.0,
            is_active=True,
        )

    membership_b = Membership.objects.filter(customer=customer_profile_b, plan=plan_b).first()
    if membership_b is None:
        membership_b = Membership.objects.create(
            customer=customer_profile_b,
            plan=plan_b,
            tenant=tenant_b,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            status=Membership.Status.ACTIVE,
            auto_renew=False,
        )

    if not Payment.objects.filter(customer=customer_profile_b).exists():
        Payment.objects.create(
            tenant=tenant_b,
            customer=customer_profile_b,
            membership=membership_b,
            amount=2000.0,
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.COMPLETED,
            transaction_id=f"txn_fitgymb_{uuid.uuid4().hex[:8]}",
            paid_at=timezone.make_aware(datetime(2026, 6, 1, 10, 0)),
        )
    else:
        payment_b = Payment.objects.filter(customer=customer_profile_b).first()
        _backfill_paid_at(payment_b, fallback_date=date(2026, 6, 1))
    echo(f"  FitGym B: {owner_b.email}, {customer_b.email} (+membership/payment)")

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "owner_a": owner_a,
        "owner_b": owner_b,
        "customer_a": customer_a,
        "customer_b": customer_b,
    }