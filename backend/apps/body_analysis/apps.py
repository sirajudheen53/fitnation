"""Body analysis app configuration."""

from django.apps import AppConfig


class BodyAnalysisConfig(AppConfig):
    """App config for the body analysis app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.body_analysis"
    verbose_name = "Body Analysis"
