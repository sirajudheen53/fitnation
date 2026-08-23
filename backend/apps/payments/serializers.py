"""Payment tracking serializers."""

from typing import ClassVar

from rest_framework import serializers

from apps.payments.models import Invoice, Payment


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
            "paid_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list] = ["id", "paid_at", "created_at", "updated_at"]


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
