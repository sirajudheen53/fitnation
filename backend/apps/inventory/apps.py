"""Inventory app configuration."""

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """App config for the inventory app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    verbose_name = "Inventory"

    def ready(self) -> None:
        """Register signal receivers when the app is loaded."""
        from apps.inventory import signals  # noqa: F401
