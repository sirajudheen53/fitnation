"""Attendance management models.

Tracks customer check-ins and trainer attendance at gym branches.
All models are tenant-scoped via ``TenantModelMixin``.
"""

from typing import Any

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin


class AttendanceRecord(TenantModelMixin):
    """A single customer check-in/check-out event at a branch."""

    class Method(models.TextChoices):
        """How the attendance was captured."""

        QR = "qr", "QR Code"
        MOBILE = "mobile", "Mobile"
        MANUAL = "manual", "Manual"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    check_in_time = models.DateTimeField()
    check_out_time = models.DateTimeField(null=True, blank=True)
    method = models.CharField(
        max_length=10,
        choices=Method.choices,
        default=Method.MANUAL,
    )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """AttendanceRecord model metadata."""

        db_table = "attendance_records"
        ordering = ["-check_in_time", "-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "customer", "date"],
                name="idx_att_customer_date",
            ),
            models.Index(
                fields=["tenant", "branch", "date"],
                name="idx_att_branch_date",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the record, defaulting ``date`` from ``check_in_time``."""
        if self.date is None and self.check_in_time is not None:
            self.date = timezone.localtime(self.check_in_time).date()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a human-readable attendance label."""
        return f"{self.customer} @ {self.check_in_time}"


class TrainerAttendance(TenantModelMixin):
    """A single trainer check-in/check-out event at a branch."""

    trainer = models.ForeignKey(
        "users.Trainer",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trainer_attendance",
    )
    check_in_time = models.DateTimeField()
    check_out_time = models.DateTimeField(null=True, blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """TrainerAttendance model metadata."""

        db_table = "trainer_attendance"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "trainer", "date"],
                name="idx_trainer_date",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the record, defaulting ``date`` from ``check_in_time``."""
        if self.date is None and self.check_in_time is not None:
            self.date = timezone.localtime(self.check_in_time).date()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a human-readable trainer attendance label."""
        return f"{self.trainer} @ {self.check_in_time}"
