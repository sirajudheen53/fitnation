"""Marketplace app configuration."""

from django.apps import AppConfig


class MarketplaceConfig(AppConfig):
    """App config for the marketplace app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.marketplace"
    verbose_name = "Marketplace"
