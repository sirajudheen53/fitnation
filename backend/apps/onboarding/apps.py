"""Onboarding app config."""

from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    """Django app configuration for the onboarding app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.onboarding"
