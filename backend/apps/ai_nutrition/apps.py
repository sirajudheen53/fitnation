"""AI Nutrition app configuration."""

from django.apps import AppConfig


class AINutritionConfig(AppConfig):
    """App config for the AI nutrition assistant."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_nutrition"
    verbose_name = "AI Nutrition"
