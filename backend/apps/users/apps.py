"""Users app configuration."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Configuration for the users app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self) -> None:
        """Connect signal handlers for this app."""
        from apps.users.signals import send_verification_email_on_register  # noqa: F401
