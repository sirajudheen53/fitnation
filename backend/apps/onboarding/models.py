"""Onboarding persistence — the resumable audit handle for the wizard."""

import uuid

from django.db import models

from apps.tenants.models import TenantModelMixin


class OnboardingSession(TenantModelMixin):
    """One front-desk onboarding run (onboarding-design §3.3).

    Three jobs: (a) the Razorpay verify step's resumable handle; (b) double-
    submit protection — a repeat POST with the same ``Idempotency-Key`` (or,
    as a safety net, the same tenant+customer+plan on the same day) replays
    the stored ``result`` instead of creating a second membership; (c) an
    audit trail of who onboarded whom.
    """

    class Status(models.TextChoices):
        """Lifecycle status of an onboarding session."""

        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboarding_sessions",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboarding_sessions",
    )
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    request_payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        db_table = "onboarding_sessions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable session label."""
        return f"Onboarding {self.uuid} ({self.status})"
