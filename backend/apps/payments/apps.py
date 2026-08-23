"""Payments app configuration."""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """App config for the payments app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payments"
