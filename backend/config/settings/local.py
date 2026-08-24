"""
FBOS Local Settings — SQLite, no Docker required.
Used for quick local development without PostgreSQL/Docker.

DJANGO_SETTINGS_MODULE=config.settings.local
"""

from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# SQLite for local dev (no Postgres needed)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/home/sirajudheen/development/fitnation/backend/db_local.sqlite3",
    }
}

# CORS: allow all in dev
CORS_ALLOW_ALL_ORIGINS = True

# DRF: relaxed dev permissions
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [  # noqa: F405
    "rest_framework.permissions.AllowAny",
]

# Email: console backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable security strictness
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = "/home/sirajudheen/development/fitnation/backend/media"