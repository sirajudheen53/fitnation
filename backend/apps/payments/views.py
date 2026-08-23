"""Payment tracking API views."""

from decimal import Decimal
from typing import ClassVar

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.payments.models import Invoice, Payment
from apps.payments.serializers import InvoiceSerializer, PaymentSerializer
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class PaymentViewSet(ModelViewSet):
    """Tenant-scoped payment CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "payments.view_payment"
    serializer_class = PaymentSerializer

    def get_queryset(self) -> Payment:
        """Return payments scoped to the request tenant with optional filters."""
        queryset = Payment.objects.for_tenant(self.request.tenant)
        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(customer_id=customer)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        paid_at_gte = self.request.query_params.get("paid_at__gte")
        if paid_at_gte:
            queryset = queryset.filter(paid_at__gte=paid_at_gte)
        paid_at_lte = self.request.query_params.get("paid_at__lte")
        if paid_at_lte:
            queryset = queryset.filter(paid_at__lte=paid_at_lte)
        return queryset

    def create(self, request: Request) -> Response:
        """Record a new payment."""
        self.required_permission = "payments.record_payment"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(tenant=request.tenant)
        self._apply_paid_at(payment)
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a payment."""
        self.required_permission = "payments.edit_payment"
        response = super().update(request, *args, **kwargs)
        self._apply_paid_at(self.get_object())
        return response

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a payment."""
        self.required_permission = "payments.edit_payment"
        response = super().partial_update(request, *args, **kwargs)
        self._apply_paid_at(self.get_object())
        return response

    @staticmethod
    def _apply_paid_at(payment: Payment) -> None:
        """Set ``paid_at`` to now when a payment is completed and no time is set."""
        if (
            payment.status == Payment.Status.COMPLETED
            and payment.paid_at is None
        ):
            payment.paid_at = timezone.now()
            payment.save(update_fields=["paid_at"])


class InvoiceViewSet(ModelViewSet):
    """Tenant-scoped invoice viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "payments.view_payment"
    serializer_class = InvoiceSerializer

    def get_queryset(self) -> Invoice:
        """Return invoices scoped to the request tenant."""
        return Invoice.objects.for_tenant(self.request.tenant)

    @action(detail=False, methods=["post"])
    def generate(self, request: Request) -> Response:
        """Generate an invoice from a payment, computing subtotal/tax/total.

        Request body:
            payment: id of the payment to invoice.
            tax_rate: optional tax percentage (default 0).
            tax: optional fixed tax amount (overrides ``tax_rate``).

        Returns:
            The created invoice.
        """
        self.required_permission = "payments.record_payment"
        payment_id = request.data.get("payment")
        if not payment_id:
            return Response(
                {"payment": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payment = Payment.objects.for_tenant(request.tenant).get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        subtotal = payment.amount
        tax = request.data.get("tax")
        if tax is None:
            tax_rate = request.data.get("tax_rate", 0)
            try:
                tax_rate = Decimal(str(tax_rate))
            except (TypeError, ValueError):
                return Response(
                    {"tax_rate": "Must be a number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tax = subtotal * (tax_rate / Decimal(100))
        else:
            try:
                tax = Decimal(str(tax))
            except (TypeError, ValueError):
                return Response(
                    {"tax": "Must be a number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        invoice = Invoice.objects.create(
            tenant=request.tenant,
            customer=payment.customer,
            payment=payment,
            subtotal=subtotal,
            tax=tax,
            total=subtotal + tax,
        )
        return Response(
            InvoiceSerializer(invoice).data,
            status=status.HTTP_201_CREATED,
        )
