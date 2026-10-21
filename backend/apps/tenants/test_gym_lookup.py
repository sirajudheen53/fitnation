"""Gym code + unauthenticated lookup (FBOS-011 mobile install-by-code).

Covers: deterministic unique code assignment (model save + migration
backfill), ``GET /api/v1/tenants/lookup/?code=`` (right gym / generic 404 /
IP-throttled 429).
"""

from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.tenants.gym_codes import (
    GYM_CODE_ALPHABET,
    GYM_CODE_LENGTH,
    assign_gym_code,
    backfill_gym_codes_for,
    generate_gym_code,
    gym_code_candidates,
)
from apps.tenants.models import Tenant
from apps.tenants.services import GYM_LOOKUP_THROTTLE_LIMIT

LOOKUP_URL = "/api/v1/tenants/lookup/"
LOC_MEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


class GymCodeGenerationTests(APITestCase):
    """Pure generator properties: deterministic, alphabet, collision-free."""

    def test_generation_is_deterministic(self) -> None:
        """The same seed always yields the same code."""
        first = generate_gym_code("6f0a2e55-7bbd-4a63-a1e7-95d1d1bd3a44:0")
        second = generate_gym_code("6f0a2e55-7bbd-4a63-a1e7-95d1d1bd3a44:0")

        self.assertEqual(first, second)

    def test_codes_use_the_safe_alphabet_and_length(self) -> None:
        """Codes are GYM_CODE_LENGTH chars from the look-alike-free alphabet."""
        for index in range(50):
            code = generate_gym_code(f"seed-{index}")

            self.assertEqual(len(code), GYM_CODE_LENGTH)
            for char in code:
                self.assertIn(char, GYM_CODE_ALPHABET)
            self.assertEqual(code, code.upper())

    def test_candidates_walk_is_collision_free(self) -> None:
        """200 candidates from two distinct seeds never collide."""
        walk_a = gym_code_candidates("uuid-a")
        walk_b = gym_code_candidates("uuid-b")
        pool = {next(walk_a) for _ in range(100)}
        pool |= {next(walk_b) for _ in range(100)}

        self.assertEqual(len(pool), 200)


class GymCodeModelTests(APITestCase):
    """Model-level assignment on save + the migration backfill helper."""

    @override_settings(CACHES=LOC_MEM)
    def test_save_assigns_a_code_when_blank(self) -> None:
        """A tenant created without a code gets one automatically."""
        tenant = Tenant.objects.create(name="Auto Gym", contact_email="auto@local.test")

        self.assertEqual(len(tenant.gym_code), GYM_CODE_LENGTH)
        self.assertEqual(tenant.gym_code, tenant.gym_code.upper())

    @override_settings(CACHES=LOC_MEM)
    def test_successive_tenants_get_distinct_codes(self) -> None:
        """Every created tenant ends up with a unique code."""
        tenants = [Tenant.objects.create(name=f"Gym {i}", contact_email=f"gym{i}@local.test") for i in range(5)]
        codes = {t.gym_code for t in tenants}

        self.assertEqual(len(codes), 5)

    @override_settings(CACHES=LOC_MEM)
    def test_tenants_do_not_repeat_a_seed_prefix_code(self) -> None:
        """Codes are hash-derived, not sequential/guessable ("GYM1"-like)."""
        tenants = [Tenant.objects.create(name=f"Enum {i}", contact_email=f"enum{i}@local.test") for i in range(3)]
        for tenant in tenants:
            for guess in ("GYM0001", "GYM0002", "AAAAAAA"):
                self.assertNotEqual(tenant.gym_code, guess)
        self.assertEqual(len({t.gym_code for t in tenants}), 3)
        self.assertTrue(all(assign_gym_code(t) == t.gym_code for t in tenants))

    @override_settings(CACHES=LOC_MEM)
    def test_backfill_assigns_only_blank_rows(self) -> None:
        """Blank rows get codes; rows that already have one are untouched."""
        # bulk_create bypasses save() → simulates pre-migration blank rows.
        blank = [Tenant(name=f"Old {i}", contact_email=f"old{i}@local.test") for i in range(3)]
        with_code = Tenant.objects.create(name="Coded", contact_email="coded@local.test")
        Tenant.objects.bulk_create(blank)

        assigned = backfill_gym_codes_for(Tenant)

        self.assertEqual(assigned, 3)
        self.assertEqual(with_code.gym_code, assign_gym_code(with_code))
        for tenant in blank:
            tenant.refresh_from_db()
            self.assertEqual(len(tenant.gym_code), GYM_CODE_LENGTH)
        # Deterministic: wiping the codes and re-running yields the same ones.
        first_codes = [t.gym_code for t in blank]
        Tenant.objects.filter(gym_code__in=first_codes).update(gym_code=None)
        self.assertEqual(backfill_gym_codes_for(Tenant), 3)
        for tenant in blank:
            tenant.refresh_from_db()
            self.assertEqual(len(tenant.gym_code), GYM_CODE_LENGTH)
        self.assertEqual([t.gym_code for t in blank], first_codes)


class TenantLookupTests(APITestCase):
    """GET /api/v1/tenants/lookup/?code= — public, throttled, non-enumerating."""

    def setUp(self) -> None:
        """Fresh cache per test (LocMem keys persist across tests otherwise)."""
        stub = override_settings(CACHES=LOC_MEM)
        stub.enable()
        self.addCleanup(stub.disable)
        cache.clear()
        self.tenant = Tenant.objects.create(name="Hash Fit", contact_email="hash@local.test")

    def test_known_code_returns_uuid_and_name(self) -> None:
        """A valid code resolves to exactly {uuid, name}."""
        response = self.client.get(LOOKUP_URL, {"code": self.tenant.gym_code})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"uuid": str(self.tenant.uuid), "name": "Hash Fit"})

    def test_lookup_is_case_insensitive(self) -> None:
        """Codes are normalized to uppercase before matching."""
        response = self.client.get(LOOKUP_URL, {"code": self.tenant.gym_code.lower()})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uuid"], str(self.tenant.uuid))

    def test_unknown_code_generic_404(self) -> None:
        """An unknown code gets the same generic error as a missing one."""
        unknown = self.client.get(LOOKUP_URL, {"code": "ZZZZZZZ"})
        missing = self.client.get(LOOKUP_URL)

        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.data, {"detail": "Gym not found."})
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.data, unknown.data)

    def test_lookup_reveals_only_public_identity(self) -> None:
        """The payload never leaks WATI/key/plan data."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "secret-wati-key"
        self.tenant.save()

        response = self.client.get(LOOKUP_URL, {"code": self.tenant.gym_code})

        self.assertEqual(set(response.data.keys()), {"uuid", "name"})
        self.assertNotIn("secret-wati-key", str(response.data))

    def test_lookup_throttles_after_limit(self) -> None:
        """More than GYM_LOOKUP_THROTTLE_LIMIT requests per IP get a 429."""
        self.client.get(LOOKUP_URL, {"code": self.tenant.gym_code})
        cache.set("gym-lookup:127.0.0.1", GYM_LOOKUP_THROTTLE_LIMIT, 600)

        response = self.client.get(LOOKUP_URL, {"code": self.tenant.gym_code})

        self.assertEqual(response.status_code, 429)

    def test_throttle_is_best_effort(self) -> None:
        """A broken cache never takes the lookup down (fail-open, like OTP)."""
        with mock.patch("django.core.cache.cache.get", side_effect=RuntimeError("down")):
            response = self.client.get(LOOKUP_URL, {"code": self.tenant.gym_code})

        self.assertEqual(response.status_code, 200)
