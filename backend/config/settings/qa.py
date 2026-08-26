"""
FBOS QA Settings
================
Used by the QA environment (single GCP VM, docker-compose.qa.yml).

DJANGO_SETTINGS_MODULE=config.settings.qa

Sits between dev (DEBUG=True, permissive) and prod (hardened).
DEBUG is False and hosts are locked down, but CORS is relaxed to a
single QA domain and TLS is terminated by nginx (so no forced redirect).
"""

from .base import *  # noqa: F401, F403
from .base import env

# ── QA overrides ─────────────────────────────────────────────────────────
DEBUG = False

# Hosts served behind nginx (TLS terminated at the proxy).
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["qa.fitnation.app", "localhost", "127.0.0.1"],
)

# ── Database: QA PostgreSQL (injected via .env.qa) ──────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# ── CORS: single known frontend origin (relaxed vs prod) ────────────────
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["https://qa.fitnation.app"],
)
CORS_ALLOW_CREDENTIALS = True

# ── Security ─────────────────────────────────────────────────────────────
# nginx terminates TLS, so Django receives HTTP from the proxy.
# We trust the proxy's X-Forwarded-Proto header for scheme detection.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# QA is not the hardened prod tier; keep cookies sent over the TLS'd proxy.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ── Static & media ───────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default="/app/staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default="/app/media")
