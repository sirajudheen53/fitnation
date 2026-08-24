"""Exercises app configuration."""

from django.apps import AppConfig


class ExercisesConfig(AppConfig):
    """App config for the exercises app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.exercises"
    verbose_name = "Exercises"
