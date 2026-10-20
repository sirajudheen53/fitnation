"""Static-manifest regression tests (prod 500 on /admin/*).

The Dockerfile used to collect static with ``2>/dev/null || true``, so a
collectstatic failure was swallowed at build time and the image shipped
without ``staticfiles.json``. Under cloudrun settings the staticfiles
backend is whitenoise's ``CompressedManifestStaticFilesStorage``, so every
template using ``{% static %}`` (admin, DRF browsable API) then raised
``ValueError: Missing staticfiles manifest entry`` at render — HTTP 500 on
all Django admin pages while plain-text endpoints kept working.

These tests pin the contract at three layers:
1. the Dockerfile must not silence collectstatic and must guard the manifest,
2. a missing manifest must fail loudly (never render a broken 500 silently),
3. after a real collectstatic, the admin login page must render.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.template import Context, Template
from django.test import Client, TestCase, override_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
MANIFEST_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


@contextlib.contextmanager
def tempfile_static_root():
    """Yield a fresh empty STATIC_ROOT dir, cleaned up afterwards."""
    root = tempfile.mkdtemp(prefix="fbos-static-")
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _manifest_storages(static_root: str) -> dict:
    """STORAGES override pinning whitenoise's manifest backend (cloudrun parity)."""
    return {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": MANIFEST_STORAGE},
    }


class DockerfileCollectstaticGuardTests(TestCase):
    """The prod incident shipped silently-broken images — pin the Dockerfile."""

    def test_collectstatic_is_loud_and_manifest_is_guarded(self) -> None:
        """collectstatic must not swallow failures; the manifest must be guarded."""
        dockerfile = (BACKEND_DIR / "Dockerfile").read_text()
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if stripped.startswith("RUN") and "collectstatic" in stripped:
                self.assertNotIn("2>/dev/null", stripped, "collectstatic errors must be loud")
                self.assertNotIn("|| true", stripped, "collectstatic failure must fail the build")
                break
        else:
            self.fail("Dockerfile has no RUN collectstatic step")
        self.assertIn("staticfiles.json", dockerfile, "image must guard the manifest file")


class ManifestStorageRenderTests(TestCase):
    """Render contract under cloudrun's manifest staticfiles storage."""

    def test_missing_manifest_raises_loudly(self) -> None:
        """No manifest → {% static %} raises ValueError (the prod 500 source)."""
        with (
            tempfile_static_root() as static_root,
            override_settings(STORAGES=_manifest_storages(static_root), STATIC_ROOT=static_root),
            self.assertRaisesRegex(ValueError, "Missing staticfiles manifest entry"),
        ):
            Template('{% load static %}{% static "admin/css/base.css" %}').render(Context())

    def test_admin_login_renders_after_collectstatic(self) -> None:
        """collectstatic must produce a manifest that lets /admin/login/ render."""
        with (
            tempfile_static_root() as static_root,
            override_settings(STORAGES=_manifest_storages(static_root), STATIC_ROOT=static_root),
        ):
            call_command("collectstatic", interactive=False, verbosity=0, clear=True)
            response = Client().get("/admin/login/")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Log in")
