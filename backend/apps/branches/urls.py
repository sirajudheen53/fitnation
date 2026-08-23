"""Branches app URL configuration."""

from django.urls import path

from apps.branches.views import BranchListCreateView, BranchRetrieveUpdateView

urlpatterns = [
    path("", BranchListCreateView.as_view(), name="branch-list-create"),
    path("<int:pk>/", BranchRetrieveUpdateView.as_view(), name="branch-detail"),
]
