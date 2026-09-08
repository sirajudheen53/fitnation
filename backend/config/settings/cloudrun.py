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
# Durable fallback (ADR-002 review): a missing/broken django-storages must
# degrade media to local disk instead of hard-failing the whole backend.
try:
    import storages.backends.gcloud  # noqa: F401

    _MEDIA_BACKEND = "storages.backends.gcloud.GoogleCloudStorage"
except Exception:  # pragma: no cover — dependency missing on a bad deploy
    _MEDIA_BACKEND = "django.core.files.storage.FileSystemStorage"

STORAGES = {
    "default": {
        "BACKEND": _MEDIA_BACKEND,
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ── Media: GCS bucket (PO-provisioned; photos survive restarts/scale) ─────────
# Private objects: django-storages signs URLs (querystring_auth) with GS_EXPIRE
# TTL — never enable public ACL.
GS_BUCKET_NAME = env("GS_BUCKET_NAME", default="yougetfitwithus-media")
GS_PROJECT_ID = env("GS_PROJECT_ID", default="yougetfitwithus")
GS_QUERYSTRING_AUTH = True
# Cloud Run compute credentials are token-only (no local RSA key) — sign
# signed URLs via the IAM signBlob API against the SA itself (roles/
# iam.serviceAccountTokenCreator granted on it).
GS_IAM_SIGN_BLOB = True
GS_SA_EMAIL = env(
    "GS_SA_EMAIL",
    default="35318880783-compute@developer.gserviceaccount.com",
)
# django-storages reads GS_EXPIRATION (GS_EXPIRE is not a recognized setting).
GS_EXPIRATION = env.int("GS_EXPIRATION", default=3600)  # ~1h signed-URL TTL

# Whitenoise middleware for serving static files (no nginx/CDN on dev Cloud Run)
MIDDLEWARE = ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE  # noqa: F405

# ── Email (SendGrid) ────────────────────────────────────────────────────────────
EMAIL_BACKEND = "sendgrid_backend.base.EmailBackend"
SENDGRID_API_KEY = env.str("SENDGRID_API_KEY", default="")
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="noreply@fitnationapp.com")
