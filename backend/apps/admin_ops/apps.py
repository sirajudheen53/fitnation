"""Admin ops app config."""

from django.apps import AppConfig


class AdminOpsConfig(AppConfig):
    """Platform admin operations."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin_ops"
