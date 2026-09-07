"""Payment tracking serializers."""

from typing import ClassVar

from django.utils import timezone
from rest_framework import serializers

from apps.customers.models import Customer
from apps.memberships.models import Membership
from apps.payments.models import Invoice, Payment, PaymentRefund, RazorpayConfig


class PaymentSerializer(serializers.ModelSerializer):
    """Serialize payment details for the frontend Payment contract (FBOS-005).

    Exposes ``customer_id``/``customer_name``, ``method``, ``membership_id``,
    ``invoice_id`` and ``payment_date`` (falling back to ``created_at`` so
    pending payments always carry a sortable date).
    """

    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.all()
    )
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    membership_id = serializers.PrimaryKeyRelatedField(
        source="membership",
        queryset=Membership.objects.all(),
        allow_null=True,
        required=False,
    )
    invoice_id = serializers.SerializerMethodField()
    method = serializers.ChoiceField(source="payment_method", choices=Payment.PaymentMethod.choices)
    payment_date = serializers.DateTimeField(source="paid_at", allow_null=True, required=False)

    class Meta:
        """Serializer metadata."""

        model = Payment
        fields: ClassVar[list] = [
            "id",
            "customer_id",
            "customer_name",
            "membership_id",
            "invoice_id",
            "amount",
            "method",
            "status",
            "transaction_id",
            "razorpay_order_id",
            "razorpay_payment_id",
            "payment_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list] = [
            "id",
            "customer_name",
            "invoice_id",
            "razorpay_order_id",
            "razorpay_payment_id",
            "created_at",
            "updated_at",
        ]

    def get_invoice_id(self, payment: Payment) -> int | None:
        """Return the first invoice issued for this payment, if any."""
        invoice = payment.invoices.first()
        return invoice.id if invoice else None

    def to_representation(self, instance):
        """Ensure payment_date is never null (frontend slices it for filters)."""
        data = super().to_representation(instance)
        if not data.get("payment_date"):
            data["payment_date"] = timezone.localtime(instance.created_at).isoformat()
        return data


class InvoiceSerializer(serializers.ModelSerializer):
    """Serialize invoice details."""

    class Meta:
        """Serializer metadata."""

        model = Invoice
        fields: ClassVar[list] = [
            "id",
            "customer",
            "payment",
            "invoice_number",
            "subtotal",
            "tax",
            "total",
            "generated_at",
        ]
        read_only_fields: ClassVar[list] = [
            "id",
            "invoice_number",
            "subtotal",
            "tax",
            "total",
            "generated_at",
        ]


class RevenueSummarySerializer(serializers.Serializer):
    """Revenue totals for today, this week and this month."""

    today = serializers.FloatField(default=0.0)
    this_week = serializers.FloatField(default=0.0)
    this_month = serializers.FloatField(default=0.0)


class CreateOrderSerializer(serializers.Serializer):
    """Validate an order-creation request."""

    customer = serializers.IntegerField()
    membership = serializers.IntegerField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class VerifyPaymentSerializer(serializers.Serializer):
    """Validate a payment-verification request."""

    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class PaymentRefundSerializer(serializers.ModelSerializer):
    """Serialize refund details."""

    class Meta:
        """Serializer metadata."""

        model = PaymentRefund
        fields: ClassVar[list] = [
            "id",
            "payment",
            "refund_id",
            "amount",
            "status",
            "reason",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list] = ["id", "created_at", "updated_at"]


class RazorpayConfigSerializer(serializers.ModelSerializer):
    """Serialize tenant Razorpay config (secrets are write-only)."""

    class Meta:
        """Serializer metadata."""

        model = RazorpayConfig
        fields: ClassVar[list] = ["id", "api_key", "is_active"]
        extra_kwargs = {"api_key": {"write_only": True}}
