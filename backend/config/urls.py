"""FBOS URL configuration — root URLs."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1 routes added as apps are created:
    # path("api/v1/auth/", include("users.urls")),
    # path("api/v1/tenants/", include("tenants.urls")),
    # path("api/v1/branches/", include("branches.urls")),
]
