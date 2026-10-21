"""Tenant app URL configuration."""

from django.urls import path

from apps.tenants.views import (
    TenantDetailView,
    TenantLookupView,
    WhatsappStatusView,
    WhatsappTestSendView,
)

urlpatterns = [
    path("me/", TenantDetailView.as_view(), name="tenant-detail"),
    path("whatsapp/test/", WhatsappTestSendView.as_view(), name="tenant-whatsapp-test"),
    path("whatsapp/status/", WhatsappStatusView.as_view(), name="tenant-whatsapp-status"),
    path("lookup/", TenantLookupView.as_view(), name="tenant-lookup"),
]
