"""Vendors app configuration."""

from django.apps import AppConfig


class VendorsConfig(AppConfig):
    """Configuration for the vendors app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vendors"
    verbose_name = "Vendors"
