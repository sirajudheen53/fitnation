"""Payments app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import (
    InvoiceViewSet,
    PaymentRefundViewSet,
    PaymentViewSet,
    RazorpayConfigView,
    RazorpayOrderView,
    RazorpayVerifyView,
    RevenueSummaryView,
)
from apps.payments.webhook_views import razorpay_webhook

router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"refunds", PaymentRefundViewSet, basename="refund")

urlpatterns = [
    # Explicit paths MUST come before the router include: the router's
    # `payments/{pk}/` detail pattern would otherwise capture single-segment
    # paths like `payments/revenue-summary/` as pk="revenue-summary" → 404.
    path("payments/revenue-summary/", RevenueSummaryView.as_view(), name="revenue-summary"),
    path("payments/razorpay/create-order/", RazorpayOrderView.as_view(), name="razorpay-create-order"),
    path("payments/razorpay/verify/", RazorpayVerifyView.as_view(), name="razorpay-verify"),
    path("payments/razorpay/config/", RazorpayConfigView.as_view(), name="razorpay-config"),
    path("", include(router.urls)),
    path(
        "payments/razorpay/webhook/",
        razorpay_webhook,
        name="razorpay-webhook",
    ),
]
