"""Django signals for user lifecycle events."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.users.models import User


@receiver(post_save, sender=User)
def send_verification_email_on_register(
    sender,
    instance: User,
    created: bool,
    **kwargs,
) -> None:
    """Send email verification when a new user is created.

    Note:
        This signal fires on every User save. The view layer is responsible for
        calling :func:`apps.core.services.email.send_verification_email` directly
        after user creation so that the HTTP request context is available for
        building the verification URL. This signal handler serves as a hook for
        future background-task integration (e.g. Celery).
    """
    if not created:
        return
    # Skip for owners (already verified at provisioning) and staff/superusers
    if instance.role == User.Role.GYM_OWNER or instance.is_owner:
        return
    if instance.is_staff or instance.is_superuser:
        return
