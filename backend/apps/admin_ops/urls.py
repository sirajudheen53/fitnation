"""Admin ops URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.admin_ops.views import AdminTenantViewSet

router = DefaultRouter()
router.register("tenants", AdminTenantViewSet, basename="admin-tenants")

app_name = "admin_ops"

urlpatterns = [
    path("", include(router.urls)),
]
