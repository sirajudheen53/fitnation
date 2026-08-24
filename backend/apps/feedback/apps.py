"""Feedback app configuration."""

from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    """Configuration for the feedback app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.feedback"
    verbose_name = "Feedback"
