"""Trainers app configuration."""

from django.apps import AppConfig


class TrainersConfig(AppConfig):
    """Configuration for the trainers app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.trainers"
    verbose_name = "Trainers"
