"""Workout Builder app configuration."""

from django.apps import AppConfig


class WorkoutsConfig(AppConfig):
    """Configuration for the workouts app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workouts"
    verbose_name = "Workouts"
