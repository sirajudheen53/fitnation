"""Admin ops models — platform-level audit records (issue #45)."""

from django.conf import settings
from django.db import models

from apps.tenants.models import Tenant


class ImpersonationLog(models.Model):
    """Audit record of a platform admin impersonating a gym owner."""

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonations_performed",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonations_received",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="impersonation_logs",
    )
    token = models.ForeignKey(
        "users.AuthToken",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impersonation_logs",
        help_text="The short-lived token issued for this session",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """ImpersonationLog model metadata."""

        db_table = "impersonation_logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return human-readable log label."""
        return f"{self.admin.email} → {self.owner.email} @ {self.tenant.name}"
