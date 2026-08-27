"""FBOS Test Settings — SQLite in-memory for fast tests."""

from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable migrations for speed (pytest-django creates tables directly)
MIGRATION_MODULES = {
    app: None
    for app in [
        "core",
        "tenants",
        "users",
        "branches",
        "customers",
        "memberships",
        "payments",
        "attendance",
        "trainers",
        "dashboard",
        "exercises",
        "workouts",
        "permissions",
        "vendors",
        "feedback",
        "diet",
        "ai_nutrition",
        "ai_coach",
        "body_analysis",
        "marketplace",
        "notifications",
        "admin",
        "auth",
        "contenttypes",
        "sessions",
    ]
}

# Speed up: disable password hashing
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Disable cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Allow all permissions in tests (views still enforce their own)
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [  # noqa: F405
    "rest_framework.permissions.AllowAny",
]

# Console email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# SendGrid settings (provide dummy values for tests)
SENDGRID_API_KEY = "SG.test-key-for-tests-only"
DEFAULT_FROM_EMAIL = "test@fitnation.local"
