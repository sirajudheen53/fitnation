"""Permissions app URL configuration."""

from django.urls import path

from apps.permissions.views import UserPermissionsView

urlpatterns = [
    path("me/permissions/", UserPermissionsView.as_view(), name="user-permissions"),
]
