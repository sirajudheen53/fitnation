"""Payment tracking API views."""

from decimal import Decimal
from typing import ClassVar

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.customers.models import Customer
from apps.payments import razorpay_service
from apps.payments.models import Invoice, Payment, PaymentRefund, RazorpayConfig
from apps.payments.serializers import (
    CreateOrderSerializer,
    InvoiceSerializer,
    PaymentRefundSerializer,
    PaymentSerializer,
    RazorpayConfigSerializer,
    VerifyPaymentSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class RazorpayOrderView(APIView):
    """Create a Razorpay order before the frontend checkout."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "payments.record_payment"

    def post(self, request: Request) -> Response:
        """Create a payment record and a corresponding Razorpay order."""
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            customer = Customer.objects.for_tenant(request.tenant).get(id=data["customer"])
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

        payment = Payment.objects.create(
            tenant=request.tenant,
            customer=customer,
            membership_id=data.get("membership"),
            amount=data["amount"],
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.PENDING,
            notes=data.get("notes", ""),
        )

        try:
            order = razorpay_service.create_order(
                request.tenant,
                payment.amount,
                receipt=str(payment.id),
            )
        except razorpay_service.RazorpayError as exc:
            payment.status = Payment.Status.FAILED
            payment.notes = (payment.notes + "\n" if payment.notes else "") + str(exc)
            payment.save()
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payment.razorpay_order_id = order.get("id", "")
        payment.save(update_fields=["razorpay_order_id", "updated_at"])

        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "razorpay_order_id": order.get("id", ""),
                "amount": order.get("amount"),
                "currency": order.get("currency", "INR"),
            },
            status=status.HTTP_201_CREATED,
        )


class RazorpayVerifyView(APIView):
    """Verify a Razorpay payment signature after the frontend checkout."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "payments.record_payment"

    def post(self, request: Request) -> Response:
        """Verify the signature and update the payment status to paid."""
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payment = Payment.objects.for_tenant(request.tenant).get(razorpay_order_id=data["razorpay_order_id"])
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            valid = razorpay_service.verify_signature(
                data["razorpay_order_id"],
                data["razorpay_payment_id"],
                data["razorpay_signature"],
                request.tenant,
            )
        except razorpay_service.RazorpayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not valid:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            return Response({"detail": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        payment.razorpay_payment_id = data["razorpay_payment_id"]
        payment.transaction_id = data["razorpay_payment_id"]
        payment.status = Payment.Status.COMPLETED
        if payment.paid_at is None:
            payment.paid_at = timezone.now()
        payment.save()

        if not Invoice.objects.filter(payment=payment).exists():
            Invoice.objects.create(
                tenant=payment.tenant,
                customer=payment.customer,
                payment=payment,
                subtotal=payment.amount,
                tax=Decimal("0.00"),
                total=payment.amount,
            )

        return Response(PaymentSerializer(payment).data)


class RazorpayConfigView(APIView):
    """Read/update the tenant Razorpay config."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]

    def _get_config(self, request: Request) -> RazorpayConfig:
        config, _ = RazorpayConfig.objects.for_tenant(request.tenant).get_or_create(tenant=request.tenant)
        return config

    def get(self, request: Request) -> Response:
        """Return the public config (api key + active flag) for the frontend."""
        config = self._get_config(request)
        return Response(
            {
                "is_active": config.is_active,
                "api_key": config.api_key,
            }
        )

    def patch(self, request: Request) -> Response:
        """Update the tenant Razorpay config (admin/owner only)."""
        self.required_permission = "payments.edit_payment"
        config = self._get_config(request)
        serializer = RazorpayConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"is_active": config.is_active})


class PaymentRefundViewSet(ModelViewSet):
    """Initiate and track refunds for payments."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "payments.record_payment"
    serializer_class = PaymentRefundSerializer
    http_method_names: ClassVar[list] = ["get", "post"]

    def get_queryset(self) -> PaymentRefund:
        """Return refunds scoped to the request tenant."""
        return PaymentRefund.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Initiate a refund for a payment."""
        payment_id = request.data.get("payment")
        if not payment_id:
            return Response(
                {"payment": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payment = Payment.objects.for_tenant(request.tenant).get(id=payment_id)
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        amount = request.data.get("amount")
        try:
            amount = Decimal(str(amount)) if amount else None
        except (TypeError, ValueError):
            return Response(
                {"amount": "Must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason", "")
        try:
            refund = razorpay_service.refund_payment(payment, amount, reason)
        except razorpay_service.RazorpayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentRefundSerializer(refund).data, status=status.HTTP_201_CREATED)


class PaymentViewSet(ModelViewSet):
    """Tenant-scoped payment CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "payments.view_payment"
    serializer_class = PaymentSerializer

    def get_queryset(self) -> Payment:
        """Return payments scoped to the request tenant with optional filters.

        Customer-role users see only their own payments.
        """
        queryset = Payment.objects.for_tenant(self.request.tenant)
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(customer__user=self.request.user)
        else:
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
        if payment.status == Payment.Status.COMPLETED and payment.paid_at is None:
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
