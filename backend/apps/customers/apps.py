"""Customers app configuration."""

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    """App config for the customers app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.customers"
    verbose_name = "Customers"
