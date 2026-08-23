"""Branches app configuration."""

from django.apps import AppConfig


class BranchesConfig(AppConfig):
    """Configuration for the branches app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.branches"
    verbose_name = "Branches"
