"""WhatsApp (WATI) config read/write on /tenants/me/ (FBOS-011 §6).

Contract = ``frontend/lib/api.ts`` ``TenantWhatsappConfig``:
``{is_wati_enabled: bool, wati_endpoint: str, wati_api_key_configured: bool}``
— the API key itself is write-only and is never echoed back.
"""

import importlib

from django.apps import apps
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.tenants.models import TenantSettings
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

# Migration module names start with a digit; import via importlib.
_enable_whatsapp_sync = importlib.import_module(
    "apps.tenants.migrations.0006_alter_tenantsettings_enable_whatsapp"
).sync_enable_whatsapp

CONFIG_URL = "/api/v1/tenants/me/"


class WhatsappConfigTestBase(APITestCase):
    """Shared fixtures: tenant + owner (is_owner) + a manager for 403 checks."""

    def setUp(self) -> None:
        """Provision the tenant plus an owner and a manager user."""
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test")
        self.owner = User.objects.create_user(
            email="owner@hash.local",
            password="F1tNati0n!",
            first_name="Own",
            last_name="Er",
            role=User.Role.GYM_OWNER,
            tenant=self.tenant,
            is_owner=True,
        )
        self.manager = User.objects.create_user(
            email="manager@hash.local",
            password="F1tNati0n!",
            first_name="Man",
            last_name="Ager",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )

    def auth(self, user: User) -> None:
        """Authenticate the test client as ``user``."""
        token = AuthToken.objects.create(user=user, tenant=user.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def get_me(self):
        """GET /tenants/me/."""
        return self.client.get(CONFIG_URL)


class WhatsappConfigReadTests(WhatsappConfigTestBase):
    """GET returns the three WATI fields and never the key value."""

    def test_get_returns_wati_fields(self) -> None:
        """GET includes is_wati_enabled, wati_endpoint, wati_api_key_configured."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_endpoint = "https://wati.example.com/api/v1/sendSessionMessage"
        self.tenant.wati_api_key = "secret-wati-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.get_me()

        self.assertEqual(response.status_code, 200)
        self.assertIn("is_wati_enabled", response.data)
        self.assertIn("wati_endpoint", response.data)
        self.assertIn("wati_api_key_configured", response.data)
        self.assertTrue(response.data["is_wati_enabled"])
        self.assertEqual(
            response.data["wati_endpoint"],
            "https://wati.example.com/api/v1/sendSessionMessage",
        )
        self.assertTrue(response.data["wati_api_key_configured"])

    def test_get_never_returns_the_key_value(self) -> None:
        """The raw key never appears anywhere in the GET payload."""
        self.tenant.wati_api_key = "secret-wati-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.get_me()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("wati_api_key", response.data)
        self.assertNotIn("secret-wati-key", str(response.data))

    def test_unconfigured_key_reads_as_false(self) -> None:
        """A tenant with no key reports wati_api_key_configured=False."""
        self.auth(self.owner)
        response = self.get_me()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_wati_enabled"])
        self.assertFalse(response.data["wati_api_key_configured"])


class WhatsappConfigWriteTests(WhatsappConfigTestBase):
    """PATCH saves the config; owner/admin only; key is write-only."""

    def test_owner_patch_saves_config(self) -> None:
        """A full PATCH stores enable, endpoint and the key (encrypted)."""
        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {
                "is_wati_enabled": True,
                "wati_endpoint": "https://wati.example.com/api",
                "wati_api_key": "first-key",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_wati_enabled)
        self.assertEqual(self.tenant.wati_endpoint, "https://wati.example.com/api")
        self.assertEqual(self.tenant.wati_api_key, "first-key")

    def test_patch_without_key_keeps_existing_key(self) -> None:
        """An omitted key must not wipe the stored secret."""
        self.tenant.wati_api_key = "existing-key"
        self.tenant.is_wati_enabled = True
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"is_wati_enabled": False, "wati_endpoint": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_wati_enabled)
        self.assertEqual(self.tenant.wati_api_key, "existing-key")

    def test_patch_with_blank_key_keeps_existing_key(self) -> None:
        """An explicitly empty string also means "leave the key unchanged"."""
        self.tenant.wati_api_key = "existing-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"is_wati_enabled": True, "wati_endpoint": "https://w.example.com", "wati_api_key": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.wati_api_key, "existing-key")
        self.assertTrue(self.tenant.is_wati_enabled)

    def test_patch_replaces_key_with_new_value(self) -> None:
        """A non-blank key replaces the stored value."""
        self.tenant.wati_api_key = "old-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"wati_api_key": "new-key"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.wati_api_key, "new-key")

    def test_patch_response_matches_get_shape(self) -> None:
        """PATCH returns the same payload the UI can refresh from (no key echo)."""
        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"is_wati_enabled": True, "wati_endpoint": "https://w.example.com", "wati_api_key": "k1"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("wati_api_key", response.data)
        self.assertNotIn("k1", str(response.data))
        self.assertTrue(response.data["wati_api_key_configured"])
        self.assertTrue(response.data["is_wati_enabled"])

    def test_non_owner_gets_403_on_patch(self) -> None:
        """A manager (staff, non-owner) cannot change the tenant config."""
        self.auth(self.manager)
        response = self.client.patch(
            CONFIG_URL,
            {"is_wati_enabled": True, "wati_endpoint": "https://w.example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_wati_enabled)

    def test_patch_requires_authentication(self) -> None:
        """Anonymous PATCHes are rejected."""
        response = self.client.patch(
            CONFIG_URL,
            {"is_wati_enabled": True},
            format="json",
        )

        self.assertEqual(response.status_code, 401)


class WhatsappFlagFoldTests(TestCase):
    """TenantSettings.enable_whatsapp is a deprecated duplicate; the 0006 sync
    folds its True values up into the live Tenant.is_wati_enabled field."""

    def test_true_settings_flag_folds_into_tenant(self) -> None:
        """Legacy gym with the old toggle on becomes is_wati_enabled=True."""
        tenant = provision_tenant(name="Legacy Gym", contact_email="legacy@local.test")
        TenantSettings.objects.filter(tenant=tenant).update(enable_whatsapp=True)
        self.assertFalse(tenant.is_wati_enabled)

        _enable_whatsapp_sync(apps, None)

        tenant.refresh_from_db()
        self.assertTrue(tenant.is_wati_enabled)

    def test_enabled_tenant_is_never_downgraded(self) -> None:
        """An already-enabled tenant keeps its flag when settings say False."""
        tenant = provision_tenant(
            name="Live Gym",
            contact_email="live@local.test",
            is_wati_enabled=True,
        )
        TenantSettings.objects.filter(tenant=tenant).update(enable_whatsapp=False)

        _enable_whatsapp_sync(apps, None)

        tenant.refresh_from_db()
        self.assertTrue(tenant.is_wati_enabled)
