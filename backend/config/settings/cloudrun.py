"""
FBOS Cloud Run Settings
=======================
Used for GCP Cloud Run deployments (dev/staging) where a managed Redis
instance is not provisioned. Uses the in-process LocMemCache so the app
runs standalone without external infrastructure. For multi-instance prod,
use config.settings.prod with a real Redis (Memorystore) instead.

DJANGO_SETTINGS_MODULE=config.settings.cloudrun
"""

import os

from .base import *  # noqa: F401, F403
from .base import env

# ── Prod-like hardening ────────────────────────────────────────────────────────
DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# ── Database (Supabase / managed Postgres via DATABASE_URL secret) ─────────────
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# ── CORS: frontend origins only ────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ── Cache: LocMemCache (single-instance friendly, no external Redis) ─────────
# Override with a real REDIS_URL (Memorystore) when scaling to multiple
# instances — set REDIS_URL and this block is replaced by django_redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fitnation-cloudrun-cache",
    }
}

# ── Security (Cloud Run terminates TLS at the Load Balancer) ──────────────────
# Cloud Run already terminates HTTPS; do not force an SSL redirect that
# would break the internal health check over HTTP.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Static (whitenoise for standalone serving, no nginx on Cloud Run) ─────────
STATIC_URL = os.environ.get("STATIC_URL", "/static/")
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/app/staticfiles")
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Whitenoise middleware for serving static files (no nginx/CDN on dev Cloud Run)
MIDDLEWARE = ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE  # noqa: F405

# ── Email (SendGrid) ────────────────────────────────────────────────────────────
EMAIL_BACKEND = "sendgrid_backend.base.EmailBackend"
SENDGRID_API_KEY = env.str("SENDGRID_API_KEY", default="")
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="noreply@fitnationapp.com")
