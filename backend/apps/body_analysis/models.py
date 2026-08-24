"""AI body analysis models.

Customers upload photos and log measurements to obtain body composition
analysis. All models are tenant-scoped via ``TenantModelMixin``.
"""

import uuid
from typing import Any

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin
from apps.users.models import User


class BodyAnalysis(TenantModelMixin):
    """A single body analysis session for a customer."""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="body_analyses",
    )
    analysis_date = models.DateField(default=timezone.localdate)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    bmi = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    body_fat_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    muscle_mass_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    posture_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    photo_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """BodyAnalysis model metadata."""

        db_table = "body_analyses"
        ordering = ["-analysis_date", "-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "user", "analysis_date"],
                name="idx_body_analysis_user_date",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist and auto-calculate BMI from height and weight."""
        if self.height_cm and self.weight_kg:
            try:
                height_m = float(self.height_cm) / 100
                weight_kg = float(self.weight_kg)
                self.bmi = round(weight_kg / (height_m * height_m), 2)
            except (TypeError, ValueError):
                self.bmi = None
        else:
            self.bmi = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return analysis label."""
        return f"BodyAnalysis: user {self.user_id} @ {self.analysis_date}"


class BodyPhoto(TenantModelMixin):
    """A customer photo uploaded for a body analysis session."""

    class PhotoType(models.TextChoices):
        """Supported photo angles."""

        FRONT = "front", "Front"
        SIDE = "side", "Side"
        BACK = "back", "Back"

    analysis = models.ForeignKey(
        BodyAnalysis,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    photo_type = models.CharField(
        max_length=10,
        choices=PhotoType.choices,
        default=PhotoType.FRONT,
    )
    image_url = models.URLField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    analysis_result = models.JSONField(null=True, blank=True)

    class Meta:
        """BodyPhoto model metadata."""

        db_table = "body_photos"
        ordering = ["-uploaded_at", "-id"]

    def __str__(self) -> str:
        """Return photo label."""
        return f"BodyPhoto: {self.photo_type} @ {self.uploaded_at}"


class BodyProgressLog(TenantModelMixin):
    """A single body metric logged over time for trend analysis."""

    class MetricType(models.TextChoices):
        """Supported progress metric types."""

        WEIGHT = "weight", "Weight"
        BMI = "bmi", "BMI"
        BODY_FAT = "body_fat", "Body Fat"
        MUSCLE = "muscle", "Muscle"
        WAIST = "waist", "Waist"
        CHEST = "chest", "Chest"
        ARM = "arm", "Arm"
        THIGH = "thigh", "Thigh"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="body_progress_logs",
    )
    date = models.DateField(default=timezone.localdate)
    metric_type = models.CharField(
        max_length=20,
        choices=MetricType.choices,
    )
    value = models.DecimalField(max_digits=7, decimal_places=2)
    unit = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """BodyProgressLog model metadata."""

        db_table = "body_progress_logs"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "user", "date"],
                name="idx_body_progress_user_date",
            ),
        ]

    def __str__(self) -> str:
        """Return progress log label."""
        return f"BodyProgressLog: {self.metric_type} {self.value} on {self.date}"
