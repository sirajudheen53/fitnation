"""Gym code exposure on the owner-facing tenants API (issue #60).

Members type the gym's ``gym_code`` during phone-OTP tenant disambiguation
(``GET /api/v1/tenants/lookup/?code=...``), so the owner must be able to read
the code from the dashboard: ``GET /tenants/me/`` (``TenantSerializer``)
includes it.
"""

from rest_framework.test import APITestCase

from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

ME_URL = "/api/v1/tenants/me/"


class GymCodeExposeTests(APITestCase):
    """``GET /tenants/me/`` returns the gym code the owner shares with members."""

    def setUp(self) -> None:
        """Provision the tenant plus its owner."""
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

    def _auth(self) -> None:
        """Authenticate the test client as the owner."""
        token = AuthToken.objects.create(user=self.owner, tenant=self.owner.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_provisioned_tenant_has_gym_code(self) -> None:
        """Every provisioned tenant carries an auto-assigned gym code."""
        self.assertTrue(self.tenant.gym_code)

    def test_get_me_includes_gym_code(self) -> None:
        """The gym code is readable by the owner on ``GET /tenants/me/``."""
        self._auth()
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["gym_code"], self.tenant.gym_code)

    def test_get_me_gym_code_matches_lookup(self) -> None:
        """The exposed code resolves the gym via the public lookup endpoint."""
        self._auth()
        me = self.client.get(ME_URL)

        lookup = self.client.get(f"/api/v1/tenants/lookup/?code={me.data['gym_code']}")
        self.assertEqual(lookup.status_code, 200)
        self.assertEqual(lookup.data["uuid"], str(self.tenant.uuid))
