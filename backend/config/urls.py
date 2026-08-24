"""FBOS URL configuration — root URLs."""

from django.contrib import admin
from django.urls import include, path

from apps.core.healthcheck import HealthCheckView
from apps.vendors.views import SubscriptionPlanListView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Health check
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    # API v1 routes
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/tenants/", include("apps.tenants.urls")),
    path("api/v1/branches/", include("apps.branches.urls")),
    path("api/v1/customers/", include("apps.customers.urls")),
    path("api/v1/memberships/", include("apps.memberships.urls")),
    path("api/v1/attendance/", include("apps.attendance.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/v1/exercises/", include("apps.exercises.urls")),
    path("api/v1/workouts/", include("apps.workouts.urls")),
    path("api/v1/", include("apps.diet.urls")),  # food-items/, diet-plans/, diet-days/, diet-meals/, diet-assignments/
    path("api/v1/", include("apps.trainers.urls")),  # trainers/, trainer-assignments/, trainer-performance/, trainer-schedules/
    path("api/v1/", include("apps.payments.urls")),  # payments/ and invoices/
    path("api/v1/permissions/", include("apps.permissions.urls")),
    path("api/v1/feedback/", include("apps.feedback.urls")),
    path("api/v1/auth/", include("apps.vendors.urls")),
    path(
        "api/v1/subscriptions/plans/",
        SubscriptionPlanListView.as_view(),
        name="subscription-plans",
    ),
]