"""Feature-flag enforcement, seeding, and settings API tests (issue #46)."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.tenants.features import (
    DEFAULT_FEATURE_FLAGS,
    FEATURE_KEYS,
    MODULE_FEATURES,
    apply_feature_overrides,
    get_feature_flags,
    is_module_enabled,
    seed_default_features,
)
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token

FLAGS_URL = "/api/v1/tenants/features/"


class ModuleFlagUnitTest(TestCase):
    """Registry semantics: default-allow, explicit disable, safe merging."""

    def test_registry_defaults_all_enabled(self) -> None:
        """Every module ships enabled so toggling is always an explicit act."""
        assert {feature.key: True for feature in MODULE_FEATURES} == DEFAULT_FEATURE_FLAGS
        assert MODULE_FEATURES


class SeedHelperTests(TestCase):
    """Direct tests of the seeding helper used by provision_tenant."""

    def test_seed_with_no_preset_returns_defaults(self) -> None:
        """``None``/empty preset → a copy of the registry defaults."""
        assert seed_default_features(None) == DEFAULT_FEATURE_FLAGS
        assert seed_default_features({}) == DEFAULT_FEATURE_FLAGS

    def test_seed_preset_wins_and_input_not_mutated(self) -> None:
        """Preset keys override defaults; the input dict is not mutated."""
        preset = {"marketplace": False, "app_access": True}
        merged = seed_default_features(preset)
        assert merged["marketplace"] is False
        assert merged["app_access"] is True
        assert "reviews" in merged
        assert set(preset) == {"marketplace", "app_access"}

    def test_absent_key_means_enabled(self) -> None:
        """A tenant with no module keys (pre-existing gyms) has everything on."""
        tenant = Tenant.objects.create(name="Legacy Gym", contact_email="legacy@local.test")
        for key in FEATURE_KEYS:
            assert is_module_enabled(tenant, key) is True

    def test_explicit_false_disables_true_enables(self) -> None:
        """Only a stored ``False`` blocks; ``True``/missing keys allow."""
        features = {"marketplace": False, "ai_coach": True}
        tenant = Tenant.objects.create(
            name="Flagged Gym",
            contact_email="flagged@local.test",
            features=features,
        )
        assert is_module_enabled(tenant, "marketplace") is False
        assert is_module_enabled(tenant, "ai_coach") is True
        assert is_module_enabled(tenant, "reviews") is True  # never touched

    def test_unknown_key_not_enforced(self) -> None:
        """Unregistered keys (other subsystems live in features too) stay allowed."""
        tenant = Tenant.objects.create(
            name="Mixed Gym",
            contact_email="mixed@local.test",
            features={"app_access": False, "biometric_cool_off_days": 5},
        )
        assert is_module_enabled(tenant, "app_access") is True

    def test_get_feature_flags_resolves_all_modules(self) -> None:
        """The resolved map covers every registered key with stored values."""
        tenant = Tenant.objects.create(
            name="Resolve Gym",
            contact_email="resolve@local.test",
            features={"marketplace": False, "app_access": True},
        )
        flags = get_feature_flags(tenant)
        assert flags == {
            "marketplace": False,
            "ai_coach": True,
            "ai_nutrition": True,
            "body_analysis": True,
            "reviews": True,
        }

    def test_apply_feature_overrides_merges_and_preserves(self) -> None:
        """Overriding one flag keeps unrelated module and non-module keys."""
        tenant = Tenant.objects.create(
            name="Merge Gym",
            contact_email="merge@local.test",
            features={"app_access": True, "reviews": True},
        )
        features = apply_feature_overrides(tenant, {"marketplace": False})
        assert features == {"app_access": True, "reviews": True, "marketplace": False}
        assert tenant.features["marketplace"] is False

    def test_apply_feature_overrides_rejects_unknown_keys(self) -> None:
        """A typo key raises instead of becoming a dead toggle."""
        tenant = Tenant.objects.create(name="Typo Gym", contact_email="typo@local.test")
        try:
            apply_feature_overrides(tenant, {"marketplacee": True})
        except KeyError as exc:
            assert "marketplacee" in str(exc)
        else:
            raise AssertionError("KeyError not raised")


class SeedingTests(TestCase):
    """Defaults seeded for new tenants (issue #46 acceptance)."""

    def test_provision_tenant_seeds_module_defaults(self) -> None:
        """Every provisioned gym starts with all module flags explicitly on."""
        tenant = provision_tenant(name="Seed Gym", contact_email="seed@local.test")
        assert tenant.features == DEFAULT_FEATURE_FLAGS

    def test_provision_preserves_preset_features(self) -> None:
        """A caller-supplied features dict wins over defaults, key by key."""
        tenant = provision_tenant(
            name="Preset Gym",
            contact_email="preset@local.test",
            features={"app_access": True, "marketplace": False},
        )
        assert tenant.features == {
            **DEFAULT_FEATURE_FLAGS,
            "app_access": True,
            "marketplace": False,
        }


class EnforcementTests(APITestCase):
    """Disabled module → 403 on that module's API; unaffected modules keep working."""

    def setUp(self) -> None:
        self.tenant = provision_tenant(name="Enforce Gym", contact_email="owner@enforce.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@enforce.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Enforce Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _disable(self, key: str) -> None:
        """Flip one module flag directly on the tenant."""
        self.tenant.features = {**self.tenant.features, key: False}
        self.tenant.save(update_fields=["features"])

    def test_marketplace_disabled_blocks_products_categories_and_cart(self) -> None:
        """All marketplace surfaces 403 with a feature_disabled code."""
        self._disable("marketplace")
        for url in ("/api/v1/marketplace/products/", "/api/v1/marketplace/categories/", "/api/v1/marketplace/cart/"):
            response = self.client.get(url)
            assert response.status_code == 403
            assert response.data["code"] == "feature_disabled"
            assert response.data["feature"] == "marketplace"

    def test_marketplace_re_enabled_after_toggle_back(self) -> None:
        """Re-enabling restores the module immediately (default-allow round-trip)."""
        self._disable("marketplace")
        assert self.client.get("/api/v1/marketplace/products/").status_code == 403
        self.tenant.features = {**self.tenant.features, "marketplace": True}
        self.tenant.save(update_fields=["features"])
        assert self.client.get("/api/v1/marketplace/products/").status_code == 200

    def test_reviews_disabled(self) -> None:
        """Reviews 403 when disabled."""
        self._disable("reviews")
        assert self.client.get("/api/v1/reviews/").status_code == 403
        assert self.client.get("/api/v1/reviews/").data["feature"] == "reviews"

    def test_ai_coach_disabled(self) -> None:
        """AI coach chat + conversations 403 when disabled."""
        self._disable("ai_coach")
        assert self.client.post("/api/v1/ai/coach/chat/", {"message": "hi"}, format="json").status_code == 403
        assert self.client.get("/api/v1/ai/coach/conversations/").status_code == 403

    def test_ai_nutrition_disabled(self) -> None:
        """AI nutrition endpoints 403 when disabled."""
        self._disable("ai_nutrition")
        assert self.client.get("/api/v1/ai/nutrition/meal-plan/").status_code == 403
        assert self.client.get("/api/v1/ai/nutrition/shopping-list/").status_code == 403

    def test_body_analysis_disabled(self) -> None:
        """Body analysis endpoints 403 when disabled."""
        self._disable("body_analysis")
        assert self.client.get("/api/v1/ai/body-analysis/").status_code == 403
        assert self.client.get("/api/v1/ai/body-progress/").status_code == 403

    def test_other_modules_unaffected_by_single_disable(self) -> None:
        """Disabling one module leaves its siblings (and non-gated apps) alone."""
        self._disable("marketplace")
        # A different gated module still works…
        assert self.client.get("/api/v1/reviews/").status_code == 200
        # …as does an app with no feature gate at all (dashboard).
        assert self.client.get("/api/v1/dashboard/overview/").status_code == 200

    def test_tenant_scoping_disable_is_per_gym(self) -> None:
        """Disabling a module for gym A does not affect gym B."""
        other = provision_tenant(name="Neighbour Gym", contact_email="owner@neighbour.test")
        other_owner = create_owner_user(
            tenant=other,
            email="owner@neighbour.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Neighbour Owner",
        )
        other_token = issue_token(other_owner, other)
        self._disable("marketplace")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        assert self.client.get("/api/v1/marketplace/products/").status_code == 200

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        assert self.client.get("/api/v1/marketplace/products/").status_code == 403


class TenantFeatureSettingsAPITests(APITestCase):
    """GET/PATCH /api/v1/tenants/features/ — contract + permissions."""

    def setUp(self) -> None:
        self.tenant = provision_tenant(name="Settings Gym", contact_email="owner@settings.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@settings.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Settings Owner",
        )
        self.manager_user = User.objects.create_user(
            email="manager@settings.test",
            password="pw123456!",
            first_name="M",
            last_name="X",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        self.customer_user = User.objects.create_user(
            email="member@settings.test",
            password="pw123456!",
            first_name="M",
            last_name="X",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def _login(self, user: User) -> None:
        """Authenticate the client with a token for the user."""
        token = issue_token(user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_owner_sees_resolved_flags_and_catalog(self) -> None:
        """GET lists every registry flag with its seeded value and metadata."""
        self._login(self.owner)
        response = self.client.get(FLAGS_URL)
        assert response.status_code == 200
        assert response.data["flags"] == DEFAULT_FEATURE_FLAGS
        catalog = {entry["key"]: entry for entry in response.data["catalog"]}
        assert set(catalog) == set(FEATURE_KEYS)
        assert catalog["marketplace"] == {
            "key": "marketplace",
            "label": "Marketplace",
            "description": "Product catalogue, cart, and member orders.",
            "default": True,
        }

    def test_patch_overrides_single_flag(self) -> None:
        """PATCH merges without dropping other module or non-module keys."""
        self.tenant.features["app_access"] = True
        self.tenant.save(update_fields=["features"])
        self._login(self.owner)
        response = self.client.patch(FLAGS_URL, {"flags": {"marketplace": False}}, format="json")
        assert response.status_code == 200
        assert response.data["flags"]["marketplace"] is False
        assert response.data["flags"]["reviews"] is True
        self.tenant.refresh_from_db()
        assert self.tenant.features["app_access"] is True  # non-module key untouched

    def test_patch_round_trip_to_enforcement(self) -> None:
        """The PATCHed flag is enforced by the module API immediately."""
        self._login(self.owner)
        assert self.client.patch(FLAGS_URL, {"flags": {"reviews": False}}, format="json").status_code == 200
        assert self.client.get("/api/v1/reviews/").status_code == 403

    def test_customer_reads_flags(self) -> None:
        """Customers (any tenant member) can read flags to hide disabled surfaces."""
        self._login(self.customer_user)
        response = self.client.get(FLAGS_URL)
        assert response.status_code == 200
        assert "flags" in response.data

    def test_customer_cannot_change_flags(self) -> None:
        """PATCH is owner-only — customers are denied."""
        self._login(self.customer_user)
        response = self.client.patch(FLAGS_URL, {"flags": {"marketplace": False}}, format="json")
        assert response.status_code == 403

    def test_manager_cannot_change_flags(self) -> None:
        """PATCH is owner-only — managers lack tenants.change_tenant."""
        self._login(self.manager_user)
        response = self.client.patch(FLAGS_URL, {"flags": {"marketplace": False}}, format="json")
        assert response.status_code == 403

    def test_patch_unknown_key_rejected(self) -> None:
        """An unregistered key is a field error, and nothing is written."""
        self._login(self.owner)
        response = self.client.patch(FLAGS_URL, {"flags": {"marketplac": True}}, format="json")
        assert response.status_code == 400
        assert "flags" in response.data
        self.tenant.refresh_from_db()
        assert self.tenant.features == DEFAULT_FEATURE_FLAGS

    def test_patch_non_boolean_value_rejected(self) -> None:
        """Only booleans are accepted — 'yes'/'true' strings are rejected."""
        self._login(self.owner)
        response = self.client.patch(FLAGS_URL, {"flags": {"marketplace": "no"}}, format="json")
        assert response.status_code == 400

    def test_unauthenticated_unauthorized(self) -> None:
        """No credentials → 401."""
        self.client.credentials()
        assert self.client.get(FLAGS_URL).status_code == 401
