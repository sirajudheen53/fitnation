"""
FBOS Development Settings
=========================
Used for local dev and docker-compose.

DJANGO_SETTINGS_MODULE=config.settings.dev
"""

from .base import *  # noqa: F401, F403
from .base import env

# ── Dev overrides ──────────────────────────────────────────────────────────────
DEBUG = True

ALLOWED_HOSTS = ["*"]

# ── Database (localhost for local dev; docker-compose overrides via env) ────────
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://fitnation:fitnation_dev@localhost:5432/fitnation",
    ),
}

# ── CORS: allow all in dev ─────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ── Django REST Framework:宽松 dev permissions ────────────────────────────────
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [  # noqa: F405
    "rest_framework.permissions.AllowAny",
]

# ── Email: console backend for dev ─────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Disable security strictness in dev ────────────────────────────────────────
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ── Django debug toolbar (optional, uncomment if installed) ────────────────────
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
# INTERNAL_IPS = ["127.0.0.1"]
