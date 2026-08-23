"""Attendance app configuration."""

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    """App config for the attendance app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.attendance"
    verbose_name = "Attendance"
