"""Access app config."""

from django.apps import AppConfig


class AccessConfig(AppConfig):
    """Access control app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.access"
