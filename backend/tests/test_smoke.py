"""
Smoke test — verifies Django settings load correctly.
Run: pytest tests/test_smoke.py
"""

from django.conf import settings


def test_django_settings_loaded():
    """Django settings are configured with a default database alias.

    Engine is intentionally not pinned: test settings run on sqlite3 while
    dev/prod settings run on postgres — the contract is that settings load
    and a default alias exists, not which engine a given module pins.
    """
    assert settings.SECRET_KEY
    assert "default" in settings.DATABASES
    assert settings.DATABASES["default"]["ENGINE"]


def test_rest_framework_configured():
    """DRF is in installed apps and configured."""
    assert "rest_framework" in settings.INSTALLED_APPS


def test_cors_configured():
    """CORS headers middleware is configured."""
    assert "corsheaders.middleware.CorsMiddleware" in settings.MIDDLEWARE


def test_tenant_middleware_placeholder():
    """Tenant middleware slot exists in MIDDLEWARE (commented until tenants app is created)."""
    # This test will be updated when tenants app is implemented
    assert "django.contrib.auth.middleware.AuthenticationMiddleware" in settings.MIDDLEWARE
