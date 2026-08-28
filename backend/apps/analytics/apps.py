"""Analytics app configuration."""

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """App config for the analytics app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    verbose_name = "Analytics"
