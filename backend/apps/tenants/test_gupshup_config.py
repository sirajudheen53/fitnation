"""Gupshup config read/write on /tenants/me/ (issue #66).

Contract mirrors the WATI block (frontend ticket #67):
``{is_gupshup_enabled: bool, gupshup_source: str, gupshup_app_name: str,
gupshup_api_key_configured: bool}`` — the API key itself is write-only and
is never echoed back.
"""


from .test_whatsapp_actions import WhatsappActionTestBase

CONFIG_URL = "/api/v1/tenants/me/"


class GupshupConfigReadTests(WhatsappActionTestBase):
    """GET returns the Gupshup fields and never the key value."""

    def test_get_returns_gupshup_fields(self) -> None:
        """GET includes enable, source, app name and the configured flag."""
        self.tenant.is_gupshup_enabled = True
        self.tenant.gupshup_source = "911234567890"
        self.tenant.gupshup_app_name = "hash-fit-app"
        self.tenant.gupshup_api_key = "secret-gup-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.get(CONFIG_URL)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_gupshup_enabled"])
        self.assertEqual(response.data["gupshup_source"], "911234567890")
        self.assertEqual(response.data["gupshup_app_name"], "hash-fit-app")
        self.assertTrue(response.data["gupshup_api_key_configured"])

    def test_get_never_returns_the_key_value(self) -> None:
        """The raw key never appears anywhere in the GET payload."""
        self.tenant.gupshup_api_key = "secret-gup-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.get(CONFIG_URL)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("gupshup_api_key", response.data)
        self.assertNotIn("secret-gup-key", str(response.data))

    def test_unconfigured_key_reads_as_false(self) -> None:
        """A tenant with no key reports gupshup_api_key_configured=False."""
        self.auth(self.owner)
        response = self.client.get(CONFIG_URL)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_gupshup_enabled"])
        self.assertFalse(response.data["gupshup_api_key_configured"])


class GupshupConfigWriteTests(WhatsappActionTestBase):
    """PATCH saves the config; owner/admin only; key is write-only."""

    def test_owner_patch_saves_config(self) -> None:
        """A full PATCH stores enable, source, app name and the key."""
        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {
                "is_gupshup_enabled": True,
                "gupshup_source": "911234567890",
                "gupshup_app_name": "hash-fit-app",
                "gupshup_api_key": "first-gup-key",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_gupshup_enabled)
        self.assertEqual(self.tenant.gupshup_source, "911234567890")
        self.assertEqual(self.tenant.gupshup_app_name, "hash-fit-app")
        self.assertEqual(self.tenant.gupshup_api_key, "first-gup-key")

    def test_patch_without_key_keeps_existing_key(self) -> None:
        """An omitted key must not wipe the stored secret."""
        self.tenant.gupshup_api_key = "existing-gup-key"
        self.tenant.is_gupshup_enabled = True
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"is_gupshup_enabled": False, "gupshup_source": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_gupshup_enabled)
        self.assertEqual(self.tenant.gupshup_api_key, "existing-gup-key")

    def test_patch_with_blank_key_keeps_existing_key(self) -> None:
        """An explicitly empty string also means "leave the key unchanged"."""
        self.tenant.gupshup_api_key = "existing-gup-key"
        self.tenant.save()

        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"is_gupshup_enabled": True, "gupshup_api_key": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.gupshup_api_key, "existing-gup-key")
        self.assertTrue(self.tenant.is_gupshup_enabled)

    def test_patch_response_matches_get_shape(self) -> None:
        """PATCH returns the refreshed payload (configured flag, no key echo)."""
        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {"is_gupshup_enabled": True, "gupshup_api_key": "gup-k1"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("gupshup_api_key", response.data)
        self.assertNotIn("gup-k1", str(response.data))
        self.assertTrue(response.data["gupshup_api_key_configured"])
        self.assertTrue(response.data["is_gupshup_enabled"])

    def test_non_owner_gets_403_on_patch(self) -> None:
        """A manager (staff, non-owner) cannot change the tenant config."""
        self.auth(self.manager)
        response = self.client.patch(CONFIG_URL, {"is_gupshup_enabled": True}, format="json")

        self.assertEqual(response.status_code, 403)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_gupshup_enabled)

    def test_wati_and_gupshup_patch_in_one_request(self) -> None:
        """Both providers configure independently in a single PATCH."""
        self.auth(self.owner)
        response = self.client.patch(
            CONFIG_URL,
            {
                "is_wati_enabled": True,
                "wati_api_key": "w1",
                "is_gupshup_enabled": True,
                "gupshup_api_key": "g1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_wati_enabled)
        self.assertTrue(self.tenant.is_gupshup_enabled)
        self.assertEqual(self.tenant.wati_api_key, "w1")
        self.assertEqual(self.tenant.gupshup_api_key, "g1")
