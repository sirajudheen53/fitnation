"""Admin ops URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.admin_ops.views import AdminPlanViewSet, AdminStatsView, AdminTenantViewSet

router = DefaultRouter()
router.register("tenants", AdminTenantViewSet, basename="admin-tenants")
router.register("plans", AdminPlanViewSet, basename="admin-plans")

app_name = "admin_ops"

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("", include(router.urls)),
]
