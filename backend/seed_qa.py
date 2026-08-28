"""
Seed QA database with test tenants and users for regression testing.
Run: python seed_qa.py
"""
import os
import sys
import uuid
from datetime import date, datetime

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.cloudrun')
django.setup()

from django.contrib.auth.hashers import make_password
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user
from apps.customers.models import Customer, BodyMeasurement, FitnessGoal
from apps.memberships.models import Membership, MembershipPlan
from apps.payments.models import Payment as PaymentModel
from apps.branches.models import Branch


def seed():
    print("=== Seeding QA Database ===")

    # ── Tenant A: FitGym A ──────────────────────────────────────────────────
    print("\n[1/2] Setting up Tenant A: FitGym A...")
    tenant_a = Tenant.objects.filter(name="FitGym A").first()
    if not tenant_a:
        tenant_a = provision_tenant(
            name="FitGym A",
            contact_email="admin@fitgyma.qa",
            subscription_plan="professional",
        )
        print(f"  Tenant A created: {tenant_a.id} — {tenant_a.name}")
    else:
        print(f"  Tenant A already exists: {tenant_a.id}")

    # Owner for Tenant A
    owner_a = User.objects.filter(email="owner_a@fitgyma.qa").first()
    if not owner_a:
        owner_a = create_owner_user(
            tenant=tenant_a,
            email="owner_a@fitgyma.qa",
            contact_name="Rahul Sharma",
            phone="+919876543210",
            password_hash=make_password("FitQA!234"),
        )
    owner_a.is_email_verified = True
    owner_a.save(update_fields=["is_email_verified"])
    print(f"  Owner A: {owner_a.email}")

    # Customer for Tenant A
    customer_a = User.objects.filter(email="customer_a@fitgyma.qa").first()
    if not customer_a:
        customer_a = User.objects.create(
            tenant=tenant_a,
            email="customer_a@fitgyma.qa",
            first_name="Priya",
            last_name="Verma",
            phone="+919876543211",
            password=make_password("FitQA!234"),
            role=User.Role.CUSTOMER,
            is_email_verified=True,
        )
        print(f"  Customer A created: {customer_a.email}")
    else:
        print(f"  Customer A already exists: {customer_a.email}")

    # Customer profile
    customer_profile = Customer.objects.filter(user=customer_a).first()
    if not customer_profile:
        customer_profile = Customer.objects.create(
            user=customer_a,
            tenant=tenant_a,
            date_of_birth=date(1995, 3, 15),
            gender="female",
            emergency_contact_name="Amit Verma",
            emergency_contact_phone="+919876543213",
            address_city="Bangalore",
            status="active",
        )
    print(f"  Customer profile: {customer_profile.id}")

    # Branch
    branch_a = Branch.objects.filter(tenant=tenant_a, name="FitGym A — Main Branch").first()
    if not branch_a:
        branch_a = Branch.objects.create(
            tenant=tenant_a,
            name="FitGym A — Main Branch",
            address_line1="123 MG Road",
            address_line2="Bangalore",
            phone="+919876543212",
            email="main@fitgyma.qa",
            is_active=True,
        )

    # MembershipPlan + Membership
    plan_a = MembershipPlan.objects.filter(tenant=tenant_a, name="Premium Annual").first()
    if not plan_a:
        plan_a = MembershipPlan.objects.create(
            tenant=tenant_a,
            name="Premium Annual",
            description="Full gym access + personal training",
            duration_days=365,
            price=15000.0,
            is_active=True,
        )

    membership_a = Membership.objects.filter(customer=customer_profile, plan=plan_a).first()
    if not membership_a:
        membership_a = Membership.objects.create(
            customer=customer_profile,
            plan=plan_a,
            tenant=tenant_a,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Membership.Status.ACTIVE,
            auto_renew=False,
        )

    # Payment
    payment_a = PaymentModel.objects.filter(customer=customer_profile).first()
    if not payment_a:
        payment_a = PaymentModel.objects.create(
            customer=customer_profile,
            membership=membership_a,
            amount=15000.0,
            payment_method=PaymentModel.PaymentMethod.ONLINE,
            status=PaymentModel.Status.COMPLETED,
            transaction_id=f"txn_fitgyma_{uuid.uuid4().hex[:8]}",
        )

    # Fitness Goal
    goal = FitnessGoal.objects.filter(customer=customer_profile, is_active=True).first()
    if not goal:
        goal = FitnessGoal.objects.create(
            customer=customer_profile,
            tenant=tenant_a,
            goal_type=FitnessGoal.GoalType.LOSE_WEIGHT,
            target_value=60.0,
            current_value=75.0,
            target_date=date(2026, 12, 31),
            notes="Lose 15kg by year end",
            is_active=True,
        )

    # Body Measurement
    measurement = BodyMeasurement.objects.filter(customer=customer_profile).first()
    if not measurement:
        measurement = BodyMeasurement.objects.create(
            customer=customer_profile,
            tenant=tenant_a,
            date_logged=datetime.now().date(),
            weight_kg=75.0,
            height_cm=165.0,
            body_fat_percentage=28.0,
        )
    print(f"  Customer A data seeded (goal, measurement, membership, payment)")

    # ── Tenant B: FitGym B ──────────────────────────────────────────────────
    print("\n[2/2] Setting up Tenant B: FitGym B...")
    tenant_b = Tenant.objects.filter(name="FitGym B").first()
    if not tenant_b:
        tenant_b = provision_tenant(
            name="FitGym B",
            contact_email="admin@fitgymb.qa",
            subscription_plan="starter",
        )
        print(f"  Tenant B created: {tenant_b.id} — {tenant_b.name}")
    else:
        print(f"  Tenant B already exists: {tenant_b.id}")

    # Owner for Tenant B
    owner_b = User.objects.filter(email="owner_b@fitgymb.qa").first()
    if not owner_b:
        owner_b = create_owner_user(
            tenant=tenant_b,
            email="owner_b@fitgymb.qa",
            contact_name="Suresh Patel",
            phone="+919876543220",
            password_hash=make_password("FitQA!234"),
        )
    owner_b.is_email_verified = True
    owner_b.save(update_fields=["is_email_verified"])
    print(f"  Owner B: {owner_b.email}")

    # Customer B
    customer_b = User.objects.filter(email="customer_b@fitgymb.qa").first()
    if not customer_b:
        customer_b = User.objects.create(
            tenant=tenant_b,
            email="customer_b@fitgymb.qa",
            first_name="Anita",
            last_name="Desai",
            phone="+919876543221",
            password=make_password("FitQA!234"),
            role=User.Role.CUSTOMER,
            is_email_verified=True,
        )

    customer_profile_b = Customer.objects.filter(user=customer_b).first()
    if not customer_profile_b:
        customer_profile_b = Customer.objects.create(
            user=customer_b,
            tenant=tenant_b,
            date_of_birth=date(1990, 7, 20),
            gender="female",
            emergency_contact_name="Ravi Desai",
            emergency_contact_phone="+919876543222",
            address_city="Mumbai",
            status="active",
        )

    branch_b = Branch.objects.filter(tenant=tenant_b, name="FitGym B — Branch").first()
    if not branch_b:
        branch_b = Branch.objects.create(
            tenant=tenant_b,
            name="FitGym B — Branch",
            address_line1="45 Linking Road",
            address_line2="Mumbai",
            phone="+919876543223",
            email="main@fitgymb.qa",
            is_active=True,
        )

    plan_b = MembershipPlan.objects.filter(tenant=tenant_b, name="Basic Monthly").first()
    if not plan_b:
        plan_b = MembershipPlan.objects.create(
            tenant=tenant_b,
            name="Basic Monthly",
            description="Gym access only",
            duration_days=30,
            price=2000.0,
            is_active=True,
        )

    membership_b = Membership.objects.filter(customer=customer_profile_b, plan=plan_b).first()
    if not membership_b:
        membership_b = Membership.objects.create(
            customer=customer_profile_b,
            plan=plan_b,
            tenant=tenant_b,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            status=Membership.Status.ACTIVE,
            auto_renew=False,
        )

    payment_b = PaymentModel.objects.filter(customer=customer_profile_b).first()
    if not payment_b:
        payment_b = PaymentModel.objects.create(
            customer=customer_profile_b,
            membership=membership_b,
            amount=2000.0,
            payment_method=PaymentModel.PaymentMethod.UPI,
            status=PaymentModel.Status.COMPLETED,
            transaction_id=f"txn_fitgymb_{uuid.uuid4().hex[:8]}",
        )
    print(f"  Tenant B data seeded")

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n=== Seed Complete ===")
    print(f"\nTenant A (FitGym A) — {tenant_a.id}")
    print(f"  Owner:    owner_a@fitgyma.qa / FitQA!234  (tenant A)")
    print(f"  Customer: customer_a@fitgyma.qa / FitQA!234  (tenant A)")
    print(f"\nTenant B (FitGym B) — {tenant_b.id}")
    print(f"  Owner:    owner_b@fitgymb.qa / FitQA!234  (tenant B)")
    print(f"  Customer: customer_b@fitgymb.qa / FitQA!234  (tenant B)")
    print(f"\n--- Regression instructions ---")
    print(f"BUG-2026-08-27-01 (cross-tenant isolation):")
    print(f"  1. Login as owner_a@fitgyma.qa / FitQA!234")
    print(f"  2. List memberships/payments — should only see FitGym A data")
    print(f"  3. Verify CANNOT see customer_b@fitgymb.qa's membership/payment")
    print(f"\nBUG-2026-08-27-02 (customer self-access):")
    print(f"  1. Login as customer_a@fitgyma.qa / FitQA!234")
    print(f"  2. Access own health profile, fitness goals, measurements")
    print(f"  3. Verify data loads correctly (goal, measurement)")
    print(f"\nFBOS-026 (email verification):")
    print(f"  1. Register new user — check is_email_verified=False in DB")
    print(f"  2. Verify token email sent via SendGrid")


if __name__ == '__main__':
    seed()
