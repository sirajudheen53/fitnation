"""Workout Builder models.

Tenant-scoped workout plans composed of days and exercises, customer
assignments, and per-session workout logs for progress tracking.
"""

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin


class WorkoutPlan(TenantModelMixin):
    """A tenant-scoped workout plan made up of days and exercises."""

    class Goal(models.TextChoices):
        """Fitness goal the plan is designed for."""

        STRENGTH = "strength", "Strength"
        HYPERTROPHY = "hypertrophy", "Hypertrophy"
        ENDURANCE = "endurance", "Endurance"
        WEIGHT_LOSS = "weight_loss", "Weight Loss"
        GENERAL_FITNESS = "general_fitness", "General Fitness"

    class Difficulty(models.TextChoices):
        """Difficulty level of the plan."""

        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    goal = models.CharField(
        max_length=20,
        choices=Goal.choices,
        default=Goal.GENERAL_FITNESS,
    )
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.BEGINNER,
    )
    duration_weeks = models.PositiveIntegerField(default=4)
    is_template = models.BooleanField(
        default=False,
        help_text="Template plans can be duplicated to create new plans.",
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workout_plans_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """WorkoutPlan model metadata."""

        db_table = "workout_plans"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable workout plan label."""
        return f"{self.name} ({self.goal})"


class WorkoutDay(TenantModelMixin):
    """A single day within a workout plan."""

    class DayOfWeek(models.TextChoices):
        """Days of the week."""

        MONDAY = "monday", "Monday"
        TUESDAY = "tuesday", "Tuesday"
        WEDNESDAY = "wednesday", "Wednesday"
        THURSDAY = "thursday", "Thursday"
        FRIDAY = "friday", "Friday"
        SATURDAY = "saturday", "Saturday"
        SUNDAY = "sunday", "Sunday"

    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name="days",
    )
    day_of_week = models.CharField(
        max_length=10,
        choices=DayOfWeek.choices,
        blank=True,
    )
    day_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Alternative to day_of_week: 1-7 for the day within the week.",
    )
    focus = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. 'Push Day', 'Leg Day', 'Full Body'.",
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        """WorkoutDay model metadata."""

        db_table = "workout_days"
        ordering = ["workout_plan", "day_number", "day_of_week"]

    def __str__(self) -> str:
        """Return a human-readable workout day label."""
        label = self.focus or self.day_of_week or f"Day {self.day_number}"
        return f"{self.workout_plan.name} — {label}"


class WorkoutExercise(TenantModelMixin):
    """An exercise within a workout day, with set/rep prescription."""

    workout_day = models.ForeignKey(
        WorkoutDay,
        on_delete=models.CASCADE,
        related_name="exercises",
    )
    exercise = models.ForeignKey(
        "exercises.Exercise",
        on_delete=models.PROTECT,
        related_name="workout_exercises",
    )
    sets = models.PositiveIntegerField(default=3)
    reps = models.CharField(
        max_length=50,
        default="8-12",
        help_text="e.g. '8-12' or '10'.",
    )
    rest_seconds = models.PositiveIntegerField(default=60)
    tempo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g. '3-1-2'.",
    )
    rpe = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Rate of perceived exertion on a 1-10 scale.",
    )
    notes = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    alternate_exercise = models.ForeignKey(
        "exercises.Exercise",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alternate_workout_exercises",
        help_text="Optional alternate exercise for supersets.",
    )

    class Meta:
        """WorkoutExercise model metadata."""

        db_table = "workout_exercises"
        ordering = ["workout_day", "order", "id"]

    def __str__(self) -> str:
        """Return a human-readable workout exercise label."""
        return f"{self.exercise.name} × {self.sets}×{self.reps}"

    def clean(self) -> None:
        """Validate RPE range and alternate exercise tenant scoping."""
        from django.core.exceptions import ValidationError

        if self.rpe is not None and not (1 <= self.rpe <= 10):
            raise ValidationError({"rpe": "RPE must be between 1 and 10."})
        if (
            self.alternate_exercise_id
            and self.alternate_exercise.tenant_id != self.tenant_id
        ):
            raise ValidationError(
                {"alternate_exercise": "Alternate exercise must belong to the same tenant."},
            )


class WorkoutAssignment(TenantModelMixin):
    """Assignment of a workout plan to a customer for a date range."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="workout_assignments",
    )
    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workout_assignments_made",
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """WorkoutAssignment model metadata."""

        db_table = "workout_assignments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable assignment label."""
        return f"{self.customer.name} ← {self.workout_plan.name}"


class WorkoutLog(TenantModelMixin):
    """A logged set performed by a customer during a workout session."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="workout_logs",
    )
    workout_exercise = models.ForeignKey(
        WorkoutExercise,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    workout_day = models.ForeignKey(
        WorkoutDay,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    date_completed = models.DateField(default=timezone.localdate)
    set_number = models.PositiveIntegerField(default=1)
    actual_reps = models.PositiveIntegerField(null=True, blank=True)
    actual_weight = models.FloatField(null=True, blank=True)
    actual_rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """WorkoutLog model metadata."""

        db_table = "workout_logs"
        ordering = ["-date_completed", "set_number"]

    def __str__(self) -> str:
        """Return a human-readable workout log label."""
        return f"{self.customer.name} — {self.workout_exercise.exercise.name} set {self.set_number}"
