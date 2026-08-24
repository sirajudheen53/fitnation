"""Notifications app configuration."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """App config for the notifications app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        """Register signal receivers when the app is loaded."""
        from apps.notifications import signals  # noqa: F401
