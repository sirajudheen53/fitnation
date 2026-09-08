"""Shared helpers + documented QA credentials for the ``seed_qa`` command."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password
from django.utils import timezone

from apps.memberships.models import Membership
from apps.payments.models import Invoice, Payment, PaymentRefund
from apps.users.models import Trainer, TrainerSchedule, User

# Documented QA credentials (see QA workspace qa-test-users.md). These are
# QA-only test accounts — the repo's seed scripts already hardcode them.
PASSWORDS = {
    "admin": "F1tNati0n!",  # platform admin (superuser)
    "tenant_ab": "FitQA!234",  # FitGym A / FitGym B regression users
    "tenant1_staff": "Test@1234",  # FitNation Test Gym staff (owner@, manager@, ...)
    "tenant2_staff": "F1tNati0n!",  # IronHouse staff (owner.iron@, ...)
    "tenant1_customers": "Test@1234",
    "tenant2_customers": "F1tNati0n!",
}


def ensure_password(user: User, password: str, reset: bool = True) -> bool:
    """Make ``user``'s password match the documented QA value.

    Args:
        user: The user to check/update.
        password: The documented QA password.
        reset: When False, leave an existing (mismatching) password untouched.

    Returns:
        True when the password was changed.
    """
    if check_password(password, user.password):
        return False
    if not reset:
        return False
    user.set_password(password)
    user.save()
    return True


def ensure_user(
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    password: str,
    tenant=None,
    phone: str = "",
    is_staff: bool | None = None,
    reset_passwords: bool = True,
) -> User:
    """Idempotently create a QA user (or make an existing one usable).

    Existing users keep their tenant/role but get re-verified and — unless
    ``reset_passwords`` is False — their password is aligned with the
    documented QA value (prevents the "seed skipped a pre-existing account"
    login mismatch).
    """
    user = User.objects.filter(email=email).first()
    if user is None:
        if is_staff is None:
            is_staff = role in ("manager", "gym_owner")
        user = User(
            tenant=tenant,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
            is_staff=is_staff,
            is_email_verified=True,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        return user

    changed: list[str] = []
    if not user.is_active:
        user.is_active = True
        changed.append("is_active")
    if not user.is_email_verified:
        user.is_email_verified = True
        changed.append("is_email_verified")
    if changed:
        user.save(update_fields=changed)
    ensure_password(user, password, reset=reset_passwords)
    return user


def ensure_trainer(user: User, **defaults) -> Trainer:
    """Idempotently create the Trainer profile for a user."""
    trainer, _ = Trainer.objects.get_or_create(user=user, defaults=defaults)
    return trainer


def ensure_trainer_schedule(trainer: Trainer, tenant, days: list[str], start: str, end: str) -> None:
    """Idempotently create weekly availability slots for a trainer."""
    for day in days:
        TrainerSchedule.objects.get_or_create(
            trainer=trainer,
            day_of_week=day,
            tenant=tenant,
            defaults={"start_time": start, "end_time": end, "is_available": True},
        )


def ensure_active(tenant) -> None:
    """Force a tenant to ACTIVE so LoginView accepts its users."""
    from apps.tenants.models import Tenant

    if tenant.status != Tenant.Status.ACTIVE:
        tenant.status = Tenant.Status.ACTIVE
        tenant.save(update_fields=["status"])


def _month_start(months_back: int) -> date:
    """First day of the month ``months_back`` months before today."""
    today = date.today()
    month = today.month - months_back
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def ensure_demo_payments(tenant, customers) -> None:
    """Idempotent demo-payment top-ups (FBOS demo-data workstream).

    Guarantees per tenant: at least one pending payment, three completed
    payments today, one completed payment in each of the last six months, a
    failed example, a refunded example with its refund record, and a
    bank-transfer payment. Invoice numbers are left to the Invoice model's
    auto-generator (INV-YYYYMMDD-NNNN) per ADR-001.
    """
    start_of_today = timezone.make_aware(datetime.combine(date.today(), time.min))
    now = timezone.now()

    def _membership_for(customer):
        return Membership.objects.filter(customer=customer).first()

    # 1. pending — feeds the overview card + pending-payments widget.
    if not Payment.objects.filter(tenant=tenant, status=Payment.Status.PENDING).exists():
        for customer in customers:
            membership = _membership_for(customer)
            if membership is None:
                continue
            Payment.objects.create(
                tenant=tenant,
                customer=customer,
                membership=membership,
                amount=membership.plan.price,
                payment_method=Payment.PaymentMethod.UPI,
                status=Payment.Status.PENDING,
                transaction_id=f"DEMO-PEND-{customer.id:05d}",
                notes="Demo pending payment",
            )
            break

    # 2. completed today (>= 3) — feeds today's revenue + the revenue series.
    if not Payment.objects.filter(tenant=tenant, status=Payment.Status.COMPLETED, paid_at__gte=start_of_today).exists():
        for customer in customers[:3]:
            membership = _membership_for(customer)
            if membership is None:
                continue
            payment = Payment.objects.create(
                tenant=tenant,
                customer=customer,
                membership=membership,
                amount=membership.plan.price,
                payment_method=Payment.PaymentMethod.ONLINE,
                status=Payment.Status.COMPLETED,
                paid_at=now,
                transaction_id=f"DEMO-TODAY-{customer.id:05d}",
                notes="Demo walk-in payment",
            )
            Invoice.objects.create(
                tenant=tenant,
                customer=customer,
                payment=payment,
                subtotal=payment.amount,
                tax=(payment.amount * Decimal("0.18")).quantize(Decimal("0.01")),
                total=(payment.amount * Decimal("1.18")).quantize(Decimal("0.01")),
            )

    # 3. six-month history (>= 1 completed payment per past month).
    for months_back in range(1, 7):
        month_day = _month_start(months_back)
        month_start = timezone.make_aware(datetime.combine(month_day, time.min))
        month_end = timezone.make_aware(datetime.combine(month_day + timedelta(days=32), time.min)).replace(day=1)
        has_payment = Payment.objects.filter(
            tenant=tenant,
            status=Payment.Status.COMPLETED,
            paid_at__gte=month_start,
            paid_at__lt=month_end,
        ).exists()
        if has_payment or not customers:
            continue
        customer = customers[months_back % len(customers)]
        membership = _membership_for(customer)
        amount = Decimal(str(membership.plan.price)) if membership else Decimal("1200.00")
        Payment.objects.create(
            tenant=tenant,
            customer=customer,
            membership=membership,
            amount=amount,
            payment_method=Payment.PaymentMethod.CARD,
            status=Payment.Status.COMPLETED,
            paid_at=timezone.make_aware(datetime.combine(month_day + timedelta(days=10), time(10, 0))),
            transaction_id=f"DEMO-HIST-{month_day:%Y%m}-{customer.id:05d}",
            notes="Demo historical payment",
        )

    # 4. failed example — exercises the failed status filter.
    if not Payment.objects.filter(tenant=tenant, status=Payment.Status.FAILED).exists():
        for customer in customers:
            membership = _membership_for(customer)
            if membership is None:
                continue
            Payment.objects.create(
                tenant=tenant,
                customer=customer,
                membership=membership,
                amount=membership.plan.price,
                payment_method=Payment.PaymentMethod.CARD,
                status=Payment.Status.FAILED,
                transaction_id=f"DEMO-FAILED-{customer.id:05d}",
                notes="Demo failed payment (card declined)",
            )
            break

    # 5. refunded example + refund record.
    if not Payment.objects.filter(tenant=tenant, status=Payment.Status.REFUNDED).exists():
        completed = (
            Payment.objects.filter(tenant=tenant, status=Payment.Status.COMPLETED, paid_at__isnull=False)
            .order_by("paid_at")
            .first()
        )
        if completed is not None:
            completed.status = Payment.Status.REFUNDED
            completed.save(update_fields=["status", "updated_at"])
            PaymentRefund.objects.create(
                tenant=tenant,
                payment=completed,
                amount=completed.amount,
                status=PaymentRefund.Status.PROCESSED,
                refund_id=f"rfp_demo_{completed.id:05d}",
                reason="Demo refund (membership cancellation)",
            )

    # 6. bank-transfer example — exercises the added method choice.
    if not Payment.objects.filter(tenant=tenant, payment_method=Payment.PaymentMethod.BANK_TRANSFER).exists():
        for customer in customers:
            membership = _membership_for(customer)
            if membership is None:
                continue
            Payment.objects.create(
                tenant=tenant,
                customer=customer,
                membership=membership,
                amount=membership.plan.price,
                payment_method=Payment.PaymentMethod.BANK_TRANSFER,
                status=Payment.Status.COMPLETED,
                paid_at=timezone.make_aware(datetime.combine(date.today(), time(11, 0))),
                transaction_id=f"DEMO-BANK-{customer.id:05d}",
                notes="Demo bank transfer",
            )
            break
