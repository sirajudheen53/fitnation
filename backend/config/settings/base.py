"""
FBOS Base Settings
==================
Shared settings inherited by dev and prod.

Architecture ref: docs/architecture.md
Multi-tenant: docs/fbos-010-multi-tenant.md
"""

from pathlib import Path

import environ

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

# ── Password Validation ─────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
