"""
FBOS Production Settings
========================
Used in staging/production containers.

DJANGO_SETTINGS_MODULE=config.settings.prod
"""

import os

from .base import *  # noqa: F401, F403
from .base import env

# ── Prod overrides ─────────────────────────────────────────────────────────────
DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ── Database (injected via env in Cloud Run / GKE) ─────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# ── CORS: strict, only frontend domains ───────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# ── Security ───────────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Static: serve via CDN or GCS in prod ────────────────────────────────────────
STATIC_URL = os.environ.get("STATIC_URL", "/static/")
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/app/staticfiles")

# ── Gunicorn (installed in Docker image) ──────────────────────────────────────
# The Dockerfile CMD uses gunicorn directly
