"""Memberships app configuration."""

from django.apps import AppConfig


class MembershipsConfig(AppConfig):
    """App config for the memberships app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.memberships"
    verbose_name = "Memberships"
