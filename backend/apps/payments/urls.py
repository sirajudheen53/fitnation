"""Payments app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import InvoiceViewSet, PaymentViewSet

router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("", include(router.urls)),
]
