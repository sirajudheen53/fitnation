"""Razorpay webhook receiver.

Razorpay sends signed webhooks for payment events. The endpoint is intentionally
unauthenticated; authenticity is enforced by verifying the ``X-Razorpay-Signature``
header using the tenant's webhook secret.

Supported events:
- ``payment.captured`` / ``payment.authorized`` → mark payment paid, generate invoice
- ``payment.failed`` → mark payment failed with failure reason
- ``refund.processed`` → mark refund/payment refunded
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.models import Invoice, Payment, PaymentRefund, RazorpayConfig


def _verify_webhook_signature(payload: bytes, signature: str, config: RazorpayConfig) -> bool:
    """Verify the Razorpay webhook signature over the raw payload.

    Args:
        payload: The raw request body.
        signature: The ``X-Razorpay-Signature`` header value.
        config: The tenant config whose webhook secret is used.

    Returns:
        ``True`` if the signature matches.
    """
    secret = config.webhook_secret or config.api_secret
    if not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _auto_generate_invoice(payment: Payment) -> Invoice | None:
    """Generate an invoice for a completed payment if none exists.

    Args:
        payment: The completed payment.

    Returns:
        The created invoice, or ``None`` if one already exists.
    """
    if Invoice.objects.filter(payment=payment).exists():
        return None
    invoice = Invoice.objects.create(
        tenant=payment.tenant,
        customer=payment.customer,
        payment=payment,
        subtotal=payment.amount,
        tax=Decimal("0.00"),
        total=payment.amount,
    )
    return invoice


def _handle_payment_captured(payload: dict[str, Any]) -> Payment | None:
    """Mark a payment as paid on ``payment.captured``/``authorized``.

    Args:
        payload: The webhook event payload.

    Returns:
        The updated payment, or ``None`` if it could not be resolved.
    """
    entity = payload.get("payment", {}).get("entity", {})
    order_id = entity.get("order_id", "")
    payment_id = entity.get("id", "")

    if not order_id:
        return None

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
    except Payment.DoesNotExist:
        return None

    payment.razorpay_payment_id = payment_id or payment.razorpay_payment_id
    payment.transaction_id = payment_id or payment.transaction_id
    payment.status = Payment.Status.COMPLETED
    if payment.paid_at is None:
        payment.paid_at = timezone.now()
    payment.save()

    _auto_generate_invoice(payment)
    return payment


def _handle_payment_failed(payload: dict[str, Any]) -> Payment | None:
    """Mark a payment as failed on ``payment.failed``.

    Args:
        payload: The webhook event payload.

    Returns:
        The updated payment, or ``None`` if it could not be resolved.
    """
    entity = payload.get("payment", {}).get("entity", {})
    order_id = entity.get("order_id", "")
    if not order_id:
        return None
    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
    except Payment.DoesNotExist:
        return None

    payment.status = Payment.Status.FAILED
    error_code = entity.get("error_code", "")
    error_description = entity.get("error_description", "")
    failure_reason = error_description or error_code or "Payment failed"
    payment.notes = (payment.notes + "\n" if payment.notes else "") + (f"Razorpay failure: {failure_reason}")
    payment.save()
    return payment


def _handle_refund_processed(payload: dict[str, Any]) -> PaymentRefund | None:
    """Mark a refund as processed on ``refund.processed``.

    Args:
        payload: The webhook event payload.

    Returns:
        The updated refund, or ``None`` if it could not be resolved.
    """
    entity = payload.get("refund", {}).get("entity", {})
    refund_id = entity.get("id", "")
    if not refund_id:
        return None
    try:
        refund = PaymentRefund.objects.get(refund_id=refund_id)
    except PaymentRefund.DoesNotExist:
        return None

    refund.status = PaymentRefund.Status.PROCESSED
    refund.save(update_fields=["status", "updated_at"])

    payment = refund.payment
    if payment.status != Payment.Status.REFUNDED:
        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=["status", "updated_at"])
    return refund


@csrf_exempt
@require_POST
def razorpay_webhook(request: Any) -> HttpResponse:
    """Handle an incoming Razorpay webhook.

    Resolves the tenant via ``X-Razorpay-Tenant`` header (or order lookup),
    verifies the signature, and applies the event to local models.

    Returns:
        HTTP 200 on accepted/successful events, 400 on bad signature, 404 when
        the tenant or order cannot be resolved.
    """
    try:
        payload = request.body
        data = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid payload"}, status=400)

    signature = request.headers.get("X-Razorpay-Signature", "")

    # Resolve tenant from explicit header, else fall back to order lookup.
    config = None
    tenant_id = request.headers.get("X-Razorpay-Tenant")
    if tenant_id:
        try:
            config = RazorpayConfig.objects.get(tenant_id=int(tenant_id))
        except (RazorpayConfig.DoesNotExist, ValueError):
            config = None

    if config is None:
        order_id = data.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id", "") or data.get(
            "payload", {}
        ).get("order", {}).get("entity", {}).get("id", "")
        if order_id:
            try:
                payment = Payment.objects.get(razorpay_order_id=order_id)
                config = RazorpayConfig.objects.for_tenant(payment.tenant).first()
            except (Payment.DoesNotExist, RazorpayConfig.DoesNotExist):
                return JsonResponse({"detail": "Not found"}, status=404)
        else:
            return JsonResponse({"detail": "Unknown tenant"}, status=404)

    if not _verify_webhook_signature(payload, signature, config):
        return JsonResponse({"detail": "Invalid signature"}, status=400)

    event = data.get("event", "")
    try:
        if event in ("payment.captured", "payment.authorized"):
            _handle_payment_captured(data.get("payload", {}))
        elif event == "payment.failed":
            _handle_payment_failed(data.get("payload", {}))
        elif event == "refund.processed":
            _handle_refund_processed(data.get("payload", {}))
    except Exception:  # noqa: BLE001 - webhooks must not 500
        # Logged by caller; return 500 so Razorpay retries.
        return JsonResponse({"detail": "Processing error"}, status=500)

    return HttpResponse(status=200)
