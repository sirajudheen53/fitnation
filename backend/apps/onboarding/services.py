"""Onboarding orchestration — one call creates the member (onboarding-design §3.1).

Transaction boundary rule: only local DB writes run inside ``atomic()``.
Razorpay order creation (network), device sync (adapter network) and
notification sends (HTTP) run after commit inside the same request; each
degrades gracefully and never rolls back a member who has already paid.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.access.models import BiometricDevice
from apps.access.selectors import get_customer_access_state
from apps.access.services import enroll_credential, sync_device
from apps.customers.serializers import CustomerSerializer
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.services.invite_service import invite_result_payload, send_app_invite
from apps.notifications.services.wati_service import send_notification
from apps.onboarding.models import OnboardingSession
from apps.onboarding.serializers import METHOD_TO_PAYMENT_METHOD, OnboardingMemberSerializer
from apps.payments.models import Invoice, Payment
from apps.payments.razorpay_service import RazorpayError, create_order

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant
    from apps.users.models import User

logger = logging.getLogger(__name__)


class OnboardingError(Exception):
    """An onboarding failure surfaced to the client with a status code."""

    def __init__(self, detail: dict | str, status_code: int = 400) -> None:
        """Store the response detail and status.

        Args:
            detail: The error body (dict or message).
            status_code: HTTP status for the response.
        """
        super().__init__(str(detail))
        self.detail = detail if isinstance(detail, dict) else {"detail": detail}
        self.status_code = status_code


def _validate_plan(tenant: "Tenant", plan_id: int) -> MembershipPlan:
    """Return the tenant's active plan or raise a 400.

    Args:
        tenant: The onboarding tenant.
        plan_id: Requested plan id.

    Returns:
        The active plan.

    Raises:
        serializers.ValidationError: Unknown plan (or not in this tenant).
    """
    plan = MembershipPlan.objects.for_tenant(tenant).filter(id=plan_id).first()
    if plan is None:
        raise serializers.ValidationError({"membership": {"plan": "Invalid plan for this gym."}})
    return plan


def _resolve_dates(plan: MembershipPlan, requested: dict) -> tuple:
    """Resolve the membership window (defaults: today → today + duration).

    Args:
        plan: The plan providing the default duration.
        requested: ``{"start_date", "end_date"}`` overrides (either optional).

    Returns:
        The ``(start_date, end_date)`` pair.

    Raises:
        serializers.ValidationError: When end_date is not after start_date.
    """
    start = requested.get("start_date") or timezone.localdate()
    end = requested.get("end_date") or (start + timezone.timedelta(days=plan.duration_days))
    if end <= start:
        raise serializers.ValidationError({"membership": {"end_date": "end_date must be after start_date."}})
    return start, end


def _create_customer(tenant: "Tenant", customer_payload: dict, request: Any) -> tuple["Customer", bool]:
    """Create (or converge) the customer via the ADR-002 serializer.

    Reusing ``CustomerSerializer.create`` keeps ONE phone-identity behaviour
    across ``POST /customers/`` and onboarding: an existing synthetic OTP
    identity is linked and adopted (returning member, no duplicate), a
    conflicting real email 400s.

    Args:
        tenant: The onboarding tenant.
        customer_payload: Validated customer payload.
        request: The DRF request (serializer context — duplicate-email checks).

    Returns:
        ``(customer, returning_member)`` — the flag distinguishes a linked
        existing profile from a fresh create for the success screen.
    """
    serializer = CustomerSerializer(data=customer_payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    known = None
    phone = customer_payload.get("phone", "")
    if phone:
        known = Customer.objects.for_tenant(tenant).filter(phone=phone, user__isnull=False).first()
    customer = serializer.save(tenant=tenant)
    returning = known is not None and known.pk == customer.pk
    return customer, returning


def _create_membership(tenant: "Tenant", customer: "Customer", plan: MembershipPlan, dates: tuple) -> Membership:
    """Create the membership row (mirrors ``MembershipViewSet.create``)."""
    start, end = dates
    membership = Membership.objects.create(
        tenant=tenant,
        customer=customer,
        plan=plan,
        start_date=start,
        end_date=end,
    )
    membership.refresh_status()
    membership.save(update_fields=["status"])
    return membership


def _create_payment(
    tenant: "Tenant",
    customer: "Customer",
    membership: Membership | None,
    plan: MembershipPlan,
    payment_payload: dict | None,
    *,
    status: str,
) -> Payment | None:
    """Create the payment row (completed + paid for desk payments).

    Args:
        tenant: The onboarding tenant.
        customer: The paying customer.
        membership: The membership being paid for (None in razorpay phase 1).
        plan: The plan (amount default).
        payment_payload: Validated payment block (or None → no payment).
        status: Initial status — ``completed`` for desk money, ``pending``
            for the razorpay two-phase start.

    Returns:
        The created ``Payment``, or ``None`` when no payment block given.
    """
    if payment_payload is None:
        return None
    amount = payment_payload.get("amount")
    if amount is None:
        amount = plan.price
    return Payment.objects.create(
        tenant=tenant,
        customer=customer,
        membership=membership,
        kind=Payment.Kind.MEMBERSHIP,
        amount=amount,
        payment_method=METHOD_TO_PAYMENT_METHOD[payment_payload["method"]],
        status=status,
        paid_at=timezone.now() if status == Payment.Status.COMPLETED else None,
        notes=payment_payload.get("notes", ""),
    )


def _enroll_biometrics(tenant: "Tenant", customer: "Customer", entries: list[dict]) -> list[dict]:
    """Enroll the desk-captured credentials (registry rows only).

    Args:
        tenant: The onboarding tenant.
        customer: The member being enrolled.
        entries: Validated biometrics entries.

    Returns:
        A list of ``{"credential_id", "device_id", "device_name", "sync"}``
        rows — ``sync`` is filled later, after commit.

    Raises:
        serializers.ValidationError: Unknown/inactive device in this tenant.
    """
    results = []
    for entry in entries:
        device = BiometricDevice.objects.for_tenant(tenant).filter(id=entry["device"], is_active=True).first()
        if device is None:
            raise serializers.ValidationError(
                {"biometrics": f"Unknown or inactive device {entry['device']} for this gym."}
            )
        if customer.branch_id and device.branch_id and device.branch_id != customer.branch_id:
            raise serializers.ValidationError(
                {"biometrics": f"Device {device.name} does not belong to the member's branch."}
            )
        credential = enroll_credential(
            tenant=tenant,
            device=device,
            customer=customer,
            credential_type=entry.get("credential_type", "fingerprint"),
            device_user_id=entry["device_user_id"],
        )
        results.append({"credential_id": credential.pk, "device_id": device.pk, "device_name": device.name, "sync": None})
    return results


def _notify(tenant: "Tenant", customer: "Customer", membership: Membership | None, send_welcome: bool) -> list[dict]:
    """Send the welcome (+ payment receipt) WhatsApp messages, best-effort.

    Args:
        tenant: The onboarding tenant.
        customer: The new member.
        membership: The created membership (None in razorpay phase 1).
        send_welcome: The wizard's opt-out flag.

    Returns:
        ``{"type", "status"}`` rows for the response's ``notifications``.
    """
    rows = []
    if send_welcome:
        log = send_notification(
            tenant,
            customer,
            "welcome",
            {
                "plan_name": membership.plan.name if membership else "",
                "end_date": membership.end_date.isoformat() if membership else "",
                "phone": customer.phone,
            },
        )
        rows.append({"type": "welcome", "status": log.status})
    return rows


def _finalize_response(
    *,
    session: OnboardingSession,
    customer: "Customer",
    membership: Membership | None,
    payment: Payment | None,
    invoice: Invoice | None,
    biometrics: list[dict],
    notifications: list[dict],
    app_invite: dict,
    status_value: str,
    razorpay_checkout: dict | None = None,
    returning_member: bool = False,
) -> dict:
    """Compose the composite response (onboarding-design §3.4 + FBOS-011 §5.1a).

    Post-commit side effects (device sync, door-access preview) are computed
    here — failures degrade to reported values, never exceptions.
    """
    from apps.memberships.selectors import get_app_entitlement

    door_access = []
    for row in biometrics:
        device = BiometricDevice.objects.filter(pk=row["device_id"]).first()
        if device is not None:
            row["sync"] = sync_device(device)
            door_access.append(
                {"device_id": device.pk, **get_customer_access_state(customer=customer, device=device)}
            )

    entitlement = get_app_entitlement(customer, tenant=customer.tenant)
    preview = entitlement.as_payload()
    preview["gym"] = {"uuid": str(customer.tenant.uuid), "name": customer.tenant.name}

    result = {
        "onboarding_id": str(session.uuid),
        "status": status_value,
        "returning_member": returning_member,
        "customer": {
            "id": customer.pk,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "branch": customer.branch_id,
            "is_active": customer.is_active,
        },
        "membership": (
            {
                "id": membership.pk,
                "plan": membership.plan_id,
                "plan_name": membership.plan.name,
                "start_date": membership.start_date.isoformat(),
                "end_date": membership.end_date.isoformat(),
                "status": membership.status,
            }
            if membership
            else None
        ),
        "payment": (
            {
                "id": payment.pk,
                "method": payment.payment_method,
                "amount": str(payment.amount),
                "status": payment.status,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            }
            if payment
            else None
        ),
        "invoice_number": invoice.invoice_number if invoice else None,
        "biometrics": biometrics,
        "door_access": door_access,
        "notifications": notifications,
        "app_invite": app_invite,
        "entitlement_preview": preview,
    }
    if razorpay_checkout is not None:
        result["razorpay_checkout"] = razorpay_checkout

    session.result = result
    session.save(update_fields=["result", "updated_at"])
    return result


def _send_app_invite(tenant: "Tenant", customer: "Customer", invited_by: "User | None", enabled: bool, poster) -> dict:
    """Fire the app invite (ride-along); failures never raise.

    Args:
        tenant: The onboarding tenant.
        customer: The member to invite.
        invited_by: The staff user (audit actor).
        enabled: The wizard's opt-out flag (``send_app_invite``).
        poster: Injectable HTTP transport (tests).

    Returns:
        The ``app_invite`` response block.
    """
    if not enabled:
        return {"status": "skipped", "reason": "disabled", "channel": None, "sent_at": None, "resend_allowed_after": None}
    try:
        result = send_app_invite(tenant, customer, invited_by=invited_by, poster=poster)
    except Exception as exc:  # noqa: BLE001 - invite failure never breaks onboarding
        logger.warning("App invite failed during onboarding for customer %s: %s", customer.pk, exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "channel": None,
            "sent_at": None,
            "resend_allowed_after": None,
        }
    return invite_result_payload(result)


def _replay_recent_session(tenant: "Tenant", customer_id: int | None, plan_id: int):
    """Find a completed session for the same member+plan today (double-click guard).

    The ``Idempotency-Key`` is the primary replay mechanism; this safety net
    makes the endpoint idempotent per phone+tenant even when the client lost
    the key (FBOS-011 brief): re-submitting the same member onto the same
    plan on the same day returns the first result instead of double-selling.

    Args:
        tenant: The onboarding tenant.
        customer_id: Resolved customer id (may be None pre-create).
        plan_id: Requested plan id.

    Returns:
        The completed ``OnboardingSession`` from today, or ``None``.
    """
    if customer_id is None:
        return None
    day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        OnboardingSession.objects.for_tenant(tenant)
        .filter(
            customer_id=customer_id,
            status=OnboardingSession.Status.COMPLETED,
            created_at__gte=day_start,
            request_payload__membership__plan=plan_id,
        )
        .order_by("-created_at")
        .first()
    )


def create_member_onboarding(
    *,
    tenant: "Tenant",
    user: "User",
    payload: dict,
    request: Any = None,
    idempotency_key: str = "",
    poster: Any = None,
) -> dict:
    """Run the whole front-desk onboarding (cash / offline / trial path).

    One transaction: customer (ADR-002 convergence) → membership → payment →
    invoice → biometric registry rows → session. After commit: device sync,
    welcome WhatsApp, and the app invite — all best-effort, reported in the
    response, never raised.

    Args:
        tenant: The onboarding tenant.
        user: The staff user running the wizard (audit).
        payload: The request body (validated here).
        request: The DRF request (customer serializer context).
        idempotency_key: ``Idempotency-Key`` header value, if sent.
        poster: Injectable notification HTTP transport (tests).

    Returns:
        The composite result dict (the response body).

    Raises:
        OnboardingError: On Razorpay order-creation failure (502 — the
            session stays re-orderable).
        serializers.ValidationError: On contract violations (400).
    """
    serializer = OnboardingMemberSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if idempotency_key:
        existing = (
            OnboardingSession.objects.for_tenant(tenant).filter(idempotency_key=idempotency_key).first()
        )
        if existing is not None:
            return session_result_payload(existing)

    plan = _validate_plan(tenant, data["membership"]["plan"])
    dates = _resolve_dates(plan, data["membership"])
    payment_payload = data.get("payment")
    method = (payment_payload or {}).get("method")
    if method == "razorpay":
        return _start_razorpay_onboarding(
            tenant=tenant,
            user=user,
            data=data,
            payload=payload,
            plan=plan,
            idempotency_key=idempotency_key,
            request=request,
        )

    with transaction.atomic():
        customer, returning = _create_customer(tenant, data["customer"].to_customer_payload(), request)

        replay = _replay_recent_session(tenant, customer.pk, plan.pk)
        if replay is not None:
            return session_result_payload(replay)

        membership = _create_membership(tenant, customer, plan, dates)
        payment = _create_payment(
            tenant,
            customer,
            membership,
            plan,
            payment_payload,
            status=Payment.Status.COMPLETED,
        )
        invoice = None
        if payment is not None:
            invoice = Invoice.objects.create(tenant=tenant, customer=customer, payment=payment,
                                             subtotal=payment.amount, total=payment.amount)
        biometrics = _enroll_biometrics(tenant, customer, data.get("biometrics") or [])
        session = OnboardingSession.objects.create(
            tenant=tenant,
            created_by=user,
            customer=customer,
            idempotency_key=idempotency_key,
            status=OnboardingSession.Status.COMPLETED,
            request_payload=_snapshot(payload),
        )

    notifications = _notify(tenant, customer, membership, data.get("send_welcome", True))
    if payment is not None and payment.status == Payment.Status.COMPLETED:
        log = send_notification(tenant, customer, "payment_received", {"amount": payment.amount})
        notifications.append({"type": "payment_received", "status": log.status})
    app_invite = _send_app_invite(tenant, customer, user, data.get("send_app_invite", True), poster)

    result = _finalize_response(
        session=session,
        customer=customer,
        membership=membership,
        payment=payment,
        invoice=invoice,
        biometrics=biometrics,
        notifications=notifications,
        app_invite=app_invite,
        status_value=OnboardingSession.Status.COMPLETED,
        returning_member=returning,
    )


def _snapshot(payload: dict) -> dict:
    """Request payload stored on the session (resume + idempotency).

    Args:
        payload: The raw request body.

    Returns:
        A JSON-safe copy.
    """
    return payload if isinstance(payload, dict) else {}


def _start_razorpay_onboarding(
    *,
    tenant: "Tenant",
    user: "User",
    data: dict,
    payload: dict,
    plan: MembershipPlan,
    idempotency_key: str,
    request: Any = None,
) -> dict:
    """Phase 1 of the two-phase Razorpay flow (onboarding-design §4.2).

    Creates customer + pending payment + session ONLY (no membership — door
    access can never go live before money is captured), then creates the
    Razorpay order. Order failure → 502, payment marked failed, session
    stays re-orderable.

    Args:
        tenant: The onboarding tenant.
        user: The staff user running the wizard.
        data: Validated payload data.
        payload: The raw request body (snapshot for phase 2).
        plan: The validated plan.
        idempotency_key: Idempotency header value.

    Returns:
        The composite result with ``razorpay_checkout``.

    Raises:
        OnboardingError: When the order cannot be created.
    """
    with transaction.atomic():
        customer, returning = _create_customer(tenant, data["customer"].to_customer_payload(), request)
        payment = _create_payment(
            tenant,
            customer,
            None,
            plan,
            data.get("payment"),
            status=Payment.Status.PENDING,
        )
        session = OnboardingSession.objects.create(
            tenant=tenant,
            created_by=user,
            customer=customer,
            idempotency_key=idempotency_key,
            status=OnboardingSession.Status.PENDING_PAYMENT,
            request_payload=_snapshot(payload),
        )

    try:
        order = create_order(tenant, payment.amount, receipt=f"onboarding:{session.uuid}")
    except RazorpayError as exc:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        logger.warning("Razorpay order creation failed for onboarding %s: %s", session.uuid, exc)
        raise OnboardingError("Payment order could not be created. Retry or take cash at the desk.", 502) from exc

    from apps.payments.razorpay_service import get_active_config

    try:
        key_id = get_active_config(tenant).api_key
    except RazorpayError:
        key_id = None
    return _finalize_response(
        session=session,
        customer=customer,
        membership=None,
        payment=payment,
        invoice=None,
        biometrics=[],
        notifications=[],
        app_invite={"status": "skipped", "reason": "pending_payment", "channel": None, "sent_at": None,
                    "resend_allowed_after": None},
        status_value=OnboardingSession.Status.PENDING_PAYMENT,
        razorpay_checkout={
            "key": key_id,
            "order_id": order.get("id"),
            "amount": order.get("amount"),
            "currency": order.get("currency", "INR"),
        },
        returning_member=returning,
    )


def complete_razorpay_onboarding(
    *,
    tenant: "Tenant",
    user: "User",
    session_uuid: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    poster: Any = None,
) -> dict:
    """Phase 2 of the Razorpay flow — verify signature, then create everything.

    Args:
        tenant: The onboarding tenant.
        user: The staff user confirming checkout.
        session_uuid: The pending session's uuid.
        razorpay_order_id: Order id from the checkout callback.
        razorpay_payment_id: Payment id from the checkout callback.
        razorpay_signature: Checkout signature (HMAC-verified locally).
        poster: Injectable notification HTTP transport (tests).

    Returns:
        The same composite result shape as the cash path.

    Raises:
        OnboardingError: 404 (unknown session for this tenant), 409 (session
            not awaiting payment), 400 (bad signature — payment marked
            failed, session stays re-orderable).
    """
    from apps.payments.razorpay_service import verify_signature

    session = OnboardingSession.objects.for_tenant(tenant).filter(uuid=session_uuid).first()
    if session is None:
        raise OnboardingError({"detail": "Onboarding session not found."}, 404)
    if session.status != OnboardingSession.Status.PENDING_PAYMENT:
        raise OnboardingError({"detail": "This onboarding session is not awaiting payment."}, 409)

    payment = Payment.objects.for_tenant(tenant).filter(
        membership__isnull=True, customer=session.customer, status=Payment.Status.PENDING
    ).order_by("-created_at").first()
    if payment is None:
        raise OnboardingError({"detail": "No pending payment found for this onboarding session."}, 409)

    if not verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature, tenant):
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        raise OnboardingError({"detail": "Payment verification failed. Retry checkout or take cash."}, 400)

    payload = session.request_payload or {}
    serializer = OnboardingMemberSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    plan = _validate_plan(tenant, data["membership"]["plan"])
    dates = _resolve_dates(plan, data["membership"])

    with transaction.atomic():
        customer = session.customer
        membership = _create_membership(tenant, customer, plan, dates)
        payment.membership = membership
        payment.status = Payment.Status.COMPLETED
        payment.paid_at = timezone.now()
        payment.razorpay_order_id = razorpay_order_id
        payment.razorpay_payment_id = razorpay_payment_id
        payment.save(
            update_fields=[
                "membership",
                "status",
                "paid_at",
                "razorpay_order_id",
                "razorpay_payment_id",
                "updated_at",
            ]
        )
        invoice = Invoice.objects.create(
            tenant=tenant,
            customer=customer,
            payment=payment,
            subtotal=payment.amount,
            total=payment.amount,
        )
        biometrics = _enroll_biometrics(tenant, customer, data.get("biometrics") or [])
        session.status = OnboardingSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])

    notifications = _notify(tenant, customer, membership, data.get("send_welcome", True))
    app_invite = _send_app_invite(tenant, customer, user, data.get("send_app_invite", True), poster)
    return _finalize_response(
        session=session,
        customer=customer,
        membership=membership,
        payment=payment,
        invoice=invoice,
        biometrics=biometrics,
        notifications=notifications,
        app_invite=app_invite,
        status_value=OnboardingSession.Status.COMPLETED,
    )
