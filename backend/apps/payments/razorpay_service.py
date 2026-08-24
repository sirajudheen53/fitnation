"""Razorpay integration service.

Encapsulates all interaction with the Razorpay SDK: order creation, payment
signature verification, and refund initiation. All calls are tenant-scoped via
the tenant's own :class:`~apps.payments.models.RazorpayConfig` (multi-tenant
isolation). The SDK client is injectable so tests can substitute a mock.
"""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from apps.payments.models import Payment, PaymentRefund, RazorpayConfig

if TYPE_CHECKING:
    from apps.tenants.models import Tenant


class RazorpayError(Exception):
    """Raised when Razorpay returns an error or config is missing."""


def _build_client(config: RazorpayConfig) -> Any:
    """Build a Razorpay client from a tenant config.

    Imported lazily so the module remains importable when the SDK is unavailable
    in unusual environments.

    Args:
        config: The tenant Razorpay config holding API credentials.

    Returns:
        A configured ``razorpay.Client`` instance.

    Raises:
        RazorpayError: If the config is inactive or lacks credentials.
    """
    from razorpay import Client

    if not config.is_active:
        raise RazorpayError("Razorpay is not enabled for this tenant")
    if not config.api_key or not config.api_secret:
        raise RazorpayError("Razorpay API credentials are not configured")

    client = Client(auth=(config.api_key, config.api_secret))
    return client


def get_active_config(tenant: Tenant) -> RazorpayConfig:
    """Return the active Razorpay config for a tenant, or raise.

    Args:
        tenant: The tenant to resolve config for.

    Returns:
        The active ``RazorpayConfig``.

    Raises:
        RazorpayError: If no active config exists for the tenant.
    """
    try:
        config = RazorpayConfig.objects.for_tenant(tenant).get(is_active=True)
    except RazorpayConfig.DoesNotExist as exc:
        raise RazorpayError("Razorpay is not enabled for this tenant") from exc
    return config


def create_order(
    tenant: Tenant,
    amount: Decimal,
    receipt: str = "",
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Create a Razorpay order for the given amount (in paise).

    Args:
        tenant: The tenant creating the order.
        amount: The order amount in the tenant's currency (e.g. INR).
        receipt: Optional receipt reference (e.g. a payment id).
        client: Optional pre-built Razorpay client (injected in tests).

    Returns:
        The Razorpay order payload (``id``, ``amount``, ``currency``, ...).

    Raises:
        RazorpayError: If the tenant has no active config or Razorpay fails.
    """
    config = get_active_config(tenant)
    client = client or _build_client(config)
    amount_paise = int((Decimal(str(amount)) * Decimal(100)).to_integral_value())
    try:
        order = client.order.create(
            data={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "payment_capture": 1,
            }
        )
    except Exception as exc:  # noqa: BLE001 - normalize SDK errors
        raise RazorpayError(f"Razorpay order creation failed: {exc}") from exc
    return order


def verify_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    tenant: Tenant,
) -> bool:
    """Verify a Razorpay payment signature to prevent tampering.

    Args:
        razorpay_order_id: The order id returned at checkout.
        razorpay_payment_id: The payment id from the checkout callback.
        razorpay_signature: The signature returned by Razorpay.
        tenant: The tenant whose webhook/verify secret is used.

    Returns:
        ``True`` if the signature is valid, otherwise ``False``.
    """
    config = get_active_config(tenant)
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    secret = config.webhook_secret or config.api_secret
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def refund_payment(
    payment: Payment,
    amount: Decimal | None = None,
    reason: str = "",
    *,
    client: Any | None = None,
) -> PaymentRefund:
    """Initiate a refund for a payment via Razorpay.

    Creates a ``PaymentRefund`` row, calls the Razorpay refund API, and updates
    the payment status to ``refunded`` when the refund is accepted.

    Args:
        payment: The payment to refund.
        amount: Optional refund amount (defaults to full payment amount).
        reason: Optional refund reason.
        client: Optional pre-built Razorpay client (injected in tests).

    Returns:
        The created ``PaymentRefund`` record.

    Raises:
        RazorpayError: If the payment has no Razorpay payment id or the refund fails.
    """
    config = get_active_config(payment.tenant)
    client = client or _build_client(config)

    if not payment.razorpay_payment_id:
        raise RazorpayError("Payment has no Razorpay payment id to refund")

    refund_amount = amount if amount is not None else payment.amount
    refund_amount_paise = int((Decimal(str(refund_amount)) * Decimal(100)).to_integral_value())

    refund = PaymentRefund.objects.create(
        tenant=payment.tenant,
        payment=payment,
        amount=refund_amount,
        status=PaymentRefund.Status.PENDING,
        reason=reason,
    )

    try:
        result = client.payment.refund(
            payment.razorpay_payment_id,
            data={
                "amount": refund_amount_paise,
                "notes": {"reason": reason, "payment_id": payment.id},
            },
        )
    except Exception as exc:  # noqa: BLE001 - normalize SDK errors
        refund.status = PaymentRefund.Status.FAILED
        refund.error_message = str(exc)
        refund.save(update_fields=["status", "error_message", "updated_at"])
        raise RazorpayError(f"Razorpay refund failed: {exc}") from exc

    refund.refund_id = result.get("id", "")
    refund.status = PaymentRefund.Status.PROCESSED
    refund.save(update_fields=["refund_id", "status", "updated_at"])

    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "updated_at"])
    return refund
