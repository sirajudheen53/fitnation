"""Dashboard app URL configuration (FBOS-008)."""

from django.urls import path

from apps.dashboard.views import (
    DashboardAttendanceView,
    DashboardMembershipsView,
    DashboardOverviewView,
    DashboardRevenueView,
    DashboardTrainersView,
)

urlpatterns = [
    path("overview/", DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("revenue/", DashboardRevenueView.as_view(), name="dashboard-revenue"),
    path("attendance/", DashboardAttendanceView.as_view(), name="dashboard-attendance"),
    path("memberships/", DashboardMembershipsView.as_view(), name="dashboard-memberships"),
    path("trainers/", DashboardTrainersView.as_view(), name="dashboard-trainers"),
]
