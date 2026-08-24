"""Exercise library models."""

from django.db import models

from apps.tenants.models import TenantModelMixin


class ExerciseCategory(TenantModelMixin):
    """A tenant-scoped category grouping exercises (e.g. Strength, Cardio)."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=220)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """ExerciseCategory model metadata."""

        db_table = "exercise_categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="uq_exercise_category_tenant_slug",
            ),
        ]

    def __str__(self) -> str:
        """Return category label."""
        return f"{self.name}"


class Exercise(TenantModelMixin):
    """A tenant-scoped exercise in the library."""

    class Difficulty(models.TextChoices):
        """Supported difficulty levels."""

        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ExerciseCategory,
        on_delete=models.CASCADE,
        related_name="exercises",
    )
    muscle_groups = models.JSONField(default=list, blank=True)
    equipment_needed = models.JSONField(default=list, blank=True)
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.BEGINNER,
    )
    instructions = models.JSONField(default=list, blank=True)
    media_url = models.URLField(null=True, blank=True)
    tips = models.TextField(blank=True)
    contraindications = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Exercise model metadata."""

        db_table = "exercises"
        ordering = ["name"]

    def __str__(self) -> str:
        """Return exercise label."""
        return f"{self.name}"
