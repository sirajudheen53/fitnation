"""Payment tracking serializers."""

from typing import ClassVar

from rest_framework import serializers

from apps.payments.models import Invoice, Payment, PaymentRefund, RazorpayConfig


class PaymentSerializer(serializers.ModelSerializer):
    """Serialize payment details."""

    class Meta:
        """Serializer metadata."""

        model = Payment
        fields: ClassVar[list] = [
            "id",
            "customer",
            "membership",
            "amount",
            "payment_method",
            "status",
            "transaction_id",
            "razorpay_order_id",
            "razorpay_payment_id",
            "paid_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list] = [
            "id",
            "paid_at",
            "razorpay_order_id",
            "razorpay_payment_id",
            "created_at",
            "updated_at",
        ]


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
