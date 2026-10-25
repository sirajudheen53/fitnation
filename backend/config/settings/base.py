"""
FBOS Base Settings
==================
Shared settings inherited by dev and prod.

Architecture ref: docs/architecture.md
Multi-tenant: docs/fbos-010-multi-tenant.md
"""

from pathlib import Path

import environ
from corsheaders.defaults import default_headers

# ── Paths ────────────────────────────────────────────────────────────────────
# backend/ is the project root for Django
# config/settings/base.py → ../../ = backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Environment ───────────────────────────────────────────────────────────────
env = environ.Env()

# Read .env file if present (local dev); in containers env vars are injected directly
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ── Core Django ───────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="django-insecure-unsafe-default")

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    # Django builtins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "django_filters",
    # Local apps
    "apps.core",
    "apps.tenants",
    "apps.users",
    "apps.branches",
    "apps.customers",
    "apps.memberships",
    "apps.payments",
    "apps.attendance",
    "apps.trainers",
    "apps.dashboard",
    "apps.feedback",
    "apps.exercises",
    "apps.workouts",
    "apps.diet",
    "apps.ai_nutrition",
    # "payments",
    # "workouts",
    # "diets",
    "apps.permissions",
    "apps.vendors",
    "apps.body_analysis",
    "apps.marketplace",
    "apps.ai_coach",
    "apps.notifications",
    "apps.analytics",
    "apps.inventory",
    "apps.reviews",
    "apps.access",
    "apps.admin_ops",
    "apps.onboarding",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.tenants.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ───────────────────────────────────────────────────────────────────
# Uses dj-database-url format: postgres://user:pass@host:port/dbname
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://fitnation:fitnation_dev@localhost:5432/fitnation"),
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Internationalization ───────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ── Static & Media ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── REST Framework ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.TenantTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

# ── CORS ───────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:8080"],
)
CORS_ALLOW_CREDENTIALS = True
# The defaults predate custom request headers: the onboarding wizard POSTs an
# `Idempotency-Key` (double-submit guard), and a browser drops the whole POST
# when the preflight doesn't allow that header — the request never reaches
# Django (issue #61).
CORS_ALLOW_HEADERS = [*default_headers, "idempotency-key"]

# ── Redis / Cache ───────────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ── Security defaults ─────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Custom User Model ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="noreply@fitnationapp.com")

# ── Password Validation ─────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── App access & invites (FBOS-011) ────────────────────────────────────────────
# Read-only grace window (calendar days) after a membership end_date. Computed
# per request — never stored (no Celery to expire a stored flag).
APP_ACCESS_GRACE_DAYS = 7

# OTP delivery chain selector (FBOS-011 §4):
#   auto    — DEBUG: console | production: tenant WATI → MSG91 SMS (default)
#   console — dev logger; ignored (with a warning) when DEBUG=False
#   stub    — returns the code in API responses; HARD-BLOCKED unless DEBUG
#   wati    — force the tenant's WATI leg only
#   sms     — force the MSG91 leg only
OTP_SENDER = env("OTP_SENDER", default="auto")
OTP_DEFAULT_COUNTRY_CODE = "91"
# Per-tenant daily WhatsApp OTP budget; when hit, delivery skips to SMS.
TENANT_WATI_OTP_DAILY_CAP = 200
# Per-tenant daily cap on OTP-auto-created customer identities (§3.1).
APP_AUTOCREATE_DAILY_LIMIT = 50

# SMS fallback provider (MSG91 flow API — platform-level, DLT-registered).
SMS_PROVIDER = env("SMS_PROVIDER", default="msg91")
MSG91_AUTH_KEY = env("MSG91_AUTH_KEY", default="")
MSG91_SENDER_ID = env("MSG91_SENDER_ID", default="")
MSG91_TEMPLATE_ID = env("MSG91_TEMPLATE_ID", default="")
MSG91_TIMEOUT = 10
# DLT-registered invite template (FBOS-011 §5.2) with NAME/GYM/LINK/PHONE vars.
MSG91_INVITE_TEMPLATE_ID = env("MSG91_INVITE_TEMPLATE_ID", default="")

# Gupshup WhatsApp BSP (issue #66) — per-tenant credentials live on the
# Tenant model; this only sizes the HTTP timeout for its /wa/api/v1/msg API.
GUPSHUP_TIMEOUT = 10

# Settings-page WhatsApp test send (issue #73). Gupshup's /wa/api/v1/msg API
# accepts (202 "submitted") any submit — including business-initiated freeform
# text it will silently never deliver — so the test must ride an APPROVED
# template in the tenant's Gupshup app, matching the template names the gym
# approved (e.g. "welcome"; verify names/params in the Gupshup console).
GUPSHUP_TEST_TEMPLATE_NAME = env("GUPSHUP_TEST_TEMPLATE_NAME", default="welcome")
# Positional {{1}}..{{n}} values for the test template, comma-separated.
GUPSHUP_TEST_TEMPLATE_PARAMS = env("GUPSHUP_TEST_TEMPLATE_PARAMS", default="")

# Approved-template delivery gate (issue #74, transport fixed in #85).
# Gupshup's /msg API 202-acks ANY submit — an unapproved template is accepted
# and silently never delivered — so the send chain verifies the template's
# APPROVED status before trusting a send, and degrades to SMS otherwise.
GUPSHUP_TEMPLATE_LIST_URL = env(
    "GUPSHUP_TEMPLATE_LIST_URL", default="https://api.gupshup.io/sm/api/v1/template/list/{appname}"
)
# How long a verified-APPROVED verdict is cached per tenant (avoid a list GET
# on every send; a newly-approved template flips within this window).
GUPSHUP_TEMPLATE_CHECK_TTL = 1800
# PORTAL account key for the template-list endpoint (issue #85): the app's
# own api key is rejected there (401 "Portal User Not Found With APIKey"),
# so the live approval check needs the account-level dashboard key. When
# unusable/absent, GUPSHUP_APPROVED_TEMPLATES below decides instead.
GUPSHUP_PORTAL_API_KEY = env("GUPSHUP_PORTAL_API_KEY", default="")
# Comma-separated template names ops has verified APPROVED in the Gupshup
# console (issue #85) — consulted when the portal-key live check cannot run
# (no portal key, or the endpoint still refuses it). Case/space tolerant.
GUPSHUP_APPROVED_TEMPLATES = env("GUPSHUP_APPROVED_TEMPLATES", default="")
# Send-param shape for the Gupshup auth OTP template (issue #86). Meta's
# AUTHENTICATION rules force a copy-code button on the recreated
# fitnation_otp template, and Gupshup fills positional params in order of
# occurrence: code_twice (default) = [code, code] (body var + button code);
# code_once = [code] (body-var-only shape, pre-button templates). Ops flips
# this after checking the console template preview — no deploy needed.
GUPSHUP_OTP_PARAM_MODE = env("GUPSHUP_OTP_PARAM_MODE", default="code_twice")

# Meta Graph API template-status verification (issue #86): the platform
# system-user token + WABA id let the approved-template delivery gate read
# status DIRECTLY from Meta — the source of truth Gupshup's console
# templates resolve to, and a working check where Gupshup's own list
# endpoint stays portal-key blocked (401). SECRET-style wiring: values live
# in gcloud secrets the coordinator attaches to the service env; the code
# only reads env. Unset → the gate falls back to the Gupshup portal-key
# live check → GUPSHUP_APPROVED_TEMPLATES → fail closed. Read-only token.
META_SYSTEM_TOKEN = env("META_SYSTEM_TOKEN", default="")
META_WABA_ID = env("META_WABA_ID", default="")
META_GRAPH_TEMPLATE_STATUS_URL = env(
    "META_GRAPH_TEMPLATE_STATUS_URL",
    default="https://graph.facebook.com/v21.0/{waba_id}/message_templates",
)
META_GRAPH_TIMEOUT = 10

# App invite deep link (FBOS-011 §5.4). The web base must host the App-Links
# verification file; the custom scheme is handled by the Android manifest.
APP_INVITE_WEB_BASE = env("APP_INVITE_WEB_BASE", default="https://app.yougetfitwithus.com")
APP_INVITE_SCHEME = "fitnation"
# The published Play package (FBOS-011 §5.4 prong 2). Must match the mobile
# app's ``applicationId`` — if the two drift apart the Play link 404s and the
# install-referrer anchor is lost.
ANDROID_PACKAGE_NAME = "com.getfitwithus.app"
# Dedupe window for app invites (front desk can force a resend past it).
APP_INVITE_RESEND_WINDOW_HOURS = 24
# Hard per-tenant daily cap on invite sends (§10.1).
APP_INVITE_DAILY_LIMIT = 20
