"""Diet app configuration."""

from django.apps import AppConfig


class DietConfig(AppConfig):
    """App config for the diet app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.diet"
    verbose_name = "Diet"
