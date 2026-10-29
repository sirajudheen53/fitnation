"""Phone normalization regression tests (issue #88).

Firebase phone-auth ID tokens carry the verified ``phone_number`` claim in
E.164 and the login ladders match rows EXACTLY — the prod blocker was a raw
``8606806956`` row that ``+918606806956`` could never hit. Covers the four
layers of the fix:

* :func:`apps.users.phone.normalize_e164` — the storage rule (unit table);
* :func:`apps.users.phone.phone_lookup_candidates` — the tolerant lookup set;
* model-save normalization on ``User.phone`` / ``Customer.phone``;
* the login + ERP-convergence endpoints resolving across BOTH formats, including
  the exact prod shape (raw-stored member, E.164 Firebase claim).
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.auth import AuthToken
from apps.users.models import User
from apps.users.phone import normalize_e164, phone_lookup_candidates
from apps.users.services import create_owner_user

FLAG_ON = {"app_access": True}


def force_legacy_phone(user: User | None = None, customer: Customer | None = None, phone: str = "") -> None:
    """Write a phone the way the pre-#88 code did — bypassing save().

    Simulates an unmigrated prod row: ``QuerySet.update`` skips the model
    save hook, so the raw typed form stays exactly as stored.
    """
    if user is not None:
        User.objects.filter(pk=user.pk).update(phone=phone)
        user.refresh_from_db()
    if customer is not None:
        Customer.objects.filter(pk=customer.pk).update(phone=phone)
        customer.refresh_from_db()


class NormalizeE164Tests(TestCase):
    """The storage rule: unambiguous Indian numbers → ``+91…``; ambiguity
    is never guessed at (a wrong guess is how login rows stop matching)."""

    def test_indian_shapes_normalize_to_e164(self) -> None:
        """Every unambiguous Indian entry form lands on ``+91XXXXXXXXXX``."""
        cases = {
            "8606806956": "+918606806956",  # bare national (the prod #88 shape)
            "0 8606806956": "+918606806956",  # trunk prefix
            "08606806956": "+918606806956",
            "918606806956": "+918606806956",  # country code without +
            "0918606806956": "+918606806956",  # 0 + 91 + national
            "+918606806956": "+918606806956",  # already E.164 (idempotent)
            "+91 86068 06956": "+918606806956",  # E.164 with separators
            "86068 06956": "+918606806956",  # separators around national
            "860-680-6956": "+918606806956",
            "(860) 680-6956": "+918606806956",
            "  +918606806956  ": "+918606806956",  # surrounding whitespace
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_e164(raw), expected)

    def test_ambiguous_values_are_untouched(self) -> None:
        """No country-code guessing: ambiguous input passes through as-is."""
        cases = ["", "   ", "12345", "1234567890", "860680695", "86068069561", "1234567890123", "not-a-phone", "0"]
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_e164(raw), raw.strip())

    def test_blank_is_blank(self) -> None:
        """Blank/None stay blank (an empty phone is not a lookup key)."""
        self.assertEqual(normalize_e164(""), "")
        self.assertEqual(normalize_e164(None), "")
        self.assertEqual(normalize_e164("   "), "")

    def test_other_countries_pass_through_separators_stripped(self) -> None:
        """Non-Indian +E.164 values are never rewritten — only cleaned."""
        self.assertEqual(normalize_e164("+1-202-555-0147"), "+12025550147")
        self.assertEqual(normalize_e164("+442071838750"), "+442071838750")

    def test_idempotent_on_normalized_values(self) -> None:
        """Normalizing twice equals normalizing once (safe as a save hook)."""
        for raw in ["8606806956", "+918606806956", "+12025550147", "12345", ""]:
            with self.subTest(raw=raw):
                once = normalize_e164(raw)
                self.assertEqual(normalize_e164(once), once)


class PhoneLookupCandidatesTests(TestCase):
    """The tolerant lookup set: every format a legacy row could sit under."""

    def test_e164_candidate_covers_all_legacy_shapes(self) -> None:
        """An E.164 claim must reach bare/0/91-stored rows and back."""
        candidates = phone_lookup_candidates("+918606806956")
        self.assertEqual(candidates[0], "+918606806956")  # migrated world first
        for legacy in ["8606806956", "08606806956", "918606806956"]:
            self.assertIn(legacy, candidates)

    def test_raw_candidate_covers_e164_rows(self) -> None:
        """The reverse transition direction: a raw typed input hits the
        already-normalized row through the canonical first candidate."""
        candidates = phone_lookup_candidates("8606806956")
        self.assertEqual(candidates[0], "+918606806956")
        self.assertIn("8606806956", candidates)

    def test_separated_input_hits_separator_stored_rows(self) -> None:
        """The literal caller form is kept so copy-pasted legacy rows match."""
        self.assertIn("86068 06956", phone_lookup_candidates("86068 06956"))

    def test_candidates_deduplicate_and_keep_order(self) -> None:
        """No duplicates; E.164 first, literal form last."""
        candidates = phone_lookup_candidates("+918606806956")
        self.assertEqual(len(candidates), len(set(candidates)))
        self.assertLess(candidates.index("+918606806956"), len(candidates) - 1)

    def test_blank_yields_no_candidates(self) -> None:
        """A blank phone must never match blank rows in a login lookup."""
        self.assertEqual(phone_lookup_candidates(""), [])
        self.assertEqual(phone_lookup_candidates(None), [])
        self.assertEqual(phone_lookup_candidates("   "), [])


class PhoneStorageModelTests(TestCase):
    """Write-path normalization: every save lands on E.164, regardless of
    the caller (API serializer or raw model use)."""

    def setUp(self) -> None:
        """A tenant to hang users/customers off."""
        self.tenant = provision_tenant(name="Phone Gym", contact_email="phone@local.test", features=FLAG_ON)

    def _create_user(self, phone: str, role: str = User.Role.CUSTOMER) -> User:
        return User.objects.create_user(
            email=f"{phone.replace('+', 'plus') or 'none'}.{role}.{self.tenant.pk}@fitnation.local",
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=role,
            tenant=self.tenant,
            phone=phone,
        )

    def test_user_save_normalizes_all_roles(self) -> None:
        """The login key is E.164 for customers — and staff roles too."""
        self.assertEqual(self._create_user("8606806956").phone, "+918606806956")
        self.assertEqual(self._create_user("+919876543210", role=User.Role.TRAINER).phone, "+919876543210")
        self.assertEqual(self._create_user("098765 43210", role=User.Role.GYM_OWNER).phone, "+919876543210")

    def test_user_update_normalizes(self) -> None:
        """An update to the raw form re-canonicalizes."""
        user = self._create_user("+919876543210")
        user.phone = "9876543210"
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.phone, "+919876543210")

    def test_ambiguous_and_blank_stay_untouched(self) -> None:
        """No guessing: ambiguous junk passes through, blank stays blank."""
        self.assertEqual(self._create_user("12345").phone, "12345")
        self.assertEqual(self._create_user("").phone, "")

    def test_customer_save_normalizes_phone(self) -> None:
        """The profile mirror normalizes identically to the user key."""
        customer = Customer.objects.create(tenant=self.tenant, name="Mir Ror", phone="8606806956")
        self.assertEqual(customer.phone, "+918606806956")

    def test_emergency_contact_phone_is_not_a_login_key(self) -> None:
        """Only the login fields normalize; contact fields keep the typed
        form (out of the #88 lookup path)."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            name="Emer Gen cy",
            phone="8606806956",
            emergency_contact_phone="0471-234 5678",
        )
        self.assertEqual(customer.emergency_contact_phone, "0471-234 5678")


class LoginToleranceEndpointTests(APITestCase):
    """The login ladders resolve BOTH formats — including the exact prod
    shape from issue #88 (raw ``8606806956`` member, E.164 Firebase claim)."""

    def setUp(self) -> None:
        """Fresh tenant + cleared caches (throttle counters leak otherwise)."""
        cache.clear()
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test", features=FLAG_ON)

    def _seed_member(self, phone: str, tenant=None) -> User:
        """A customer member whose stored phone is forced back to ``phone``."""
        tenant = tenant or self.tenant
        user = User.objects.create_user(
            email=f"member.{tenant.pk}.{phone.strip('+') or 'none'}@fitnation.local",
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=User.Role.CUSTOMER,
            tenant=tenant,
            phone=phone,
        )
        customer = Customer.objects.create(tenant=tenant, user=user, name="Mem Ber", phone=phone)
        force_legacy_phone(user=user, customer=customer, phone=phone)
        return user

    def _firebase_login(self, claim: str, gym: str | None = None):
        """POST the firebase route with the verifier mocked to ``claim``."""
        payload = {"id_token": "firebase-id-token"}
        if gym:
            payload["gym"] = gym
        with patch("apps.users.views.firebase_verify_phone", return_value=claim):
            return self.client.post("/api/v1/auth/firebase/", payload, format="json")

    def test_e164_claim_matches_raw_stored_member(self) -> None:
        """THE prod blocker (#88): raw ``8606806956`` row + ``+91…`` claim
        converges to the existing member instead of a generic 400."""
        member = self._seed_member("8606806956")
        before = User.objects.count()

        response = self._firebase_login("+918606806956", gym=str(self.tenant.uuid))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["id"], member.pk)
        self.assertEqual(User.objects.count(), before)  # converged, not duplicated

    def test_raw_otp_input_matches_e164_stored_member(self) -> None:
        """The OTP route (same ladder): a raw typed input hits an
        already-normalized row — the reverse transition direction."""
        member = self._seed_member("+919876500000")
        overrides = {"DEBUG": True, "OTP_SENDER": "stub", "OTP_RESEND_COOLDOWN_SECONDS": 0}
        with self.settings(**overrides):
            issued = self.client.post(
                "/api/v1/users/auth/otp/request/",
                {"phone": "9876500000", "gym": str(self.tenant.uuid)},
                format="json",
            )
            self.assertEqual(issued.status_code, 200, issued.data)
            verified = self.client.post(
                "/api/v1/users/auth/otp/verify/",
                {"phone": "9876500000", "otp": issued.data["otp"], "gym": str(self.tenant.uuid)},
                format="json",
            )
        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertEqual(verified.data["user"]["id"], member.pk)

    def test_otp_request_and_verify_bind_on_the_same_normalized_phone(self) -> None:
        """Request with the raw form, verify with E.164 (or vice versa):
        both canonicalize to the same OtpCode binding."""
        self._seed_member("+919876500001")
        overrides = {"DEBUG": True, "OTP_SENDER": "stub", "OTP_RESEND_COOLDOWN_SECONDS": 0}
        with self.settings(**overrides):
            issued = self.client.post(
                "/api/v1/users/auth/otp/request/",
                {"phone": "9876500001", "gym": str(self.tenant.uuid)},
                format="json",
            )
            self.assertEqual(issued.status_code, 200, issued.data)
            verified = self.client.post(
                "/api/v1/users/auth/otp/verify/",
                {"phone": "+919876500001", "otp": issued.data["otp"], "gym": str(self.tenant.uuid)},
                format="json",
            )
        self.assertEqual(verified.status_code, 200, verified.data)

    def test_mixed_format_rows_still_disambiguate_across_gyms(self) -> None:
        """The same human at two gyms — one row raw, one E.164 — yields the
        200 select_gym payload, never a duplicate identity or a 400."""
        other = provision_tenant(name="Gym B", contact_email="b@local.test", features=FLAG_ON)
        self._seed_member("9876500002")
        self._seed_member("+919876500002", tenant=other)

        response = self._firebase_login("+919876500002")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "select_gym")
        self.assertCountEqual(
            [g["tenant"] for g in response.data["gyms"]],
            [str(self.tenant.uuid), str(other.uuid)],
        )
        self.assertNotIn("token", response.data)

    def test_new_firebase_logins_store_e164(self) -> None:
        """An unknown phone auto-provisions with the canonical stored form —
        new rows are clean from birth, no migration needed."""
        response = self._firebase_login("+919876500003", gym=str(self.tenant.uuid))

        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(pk=response.data["user"]["id"])
        self.assertEqual(user.phone, "+919876500003")
        self.assertEqual(AuthToken.objects.get(key=response.data["token"]).user, user)


class GymCodeAnchorTests(APITestCase):
    """The #87 first-time dead-end: a phone with no customer row in ANY gym
    used to 400 with "Specify your gym to continue" and no way forward. The
    anchor now also accepts the gym's short signup code (the one owners share
    from the dashboard's Gym Code card), so the typed recovery path resolves
    and auto-provisions exactly like a uuid anchor."""

    def setUp(self) -> None:
        """Fresh tenant + cleared caches (throttle counters leak otherwise)."""
        cache.clear()
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test", features=FLAG_ON)

    def _firebase_login(self, claim: str, gym: str | None = None):
        """POST the firebase route with the verifier mocked to ``claim``."""
        payload = {"id_token": "firebase-id-token"}
        if gym:
            payload["gym"] = gym
        with patch("apps.users.views.firebase_verify_phone", return_value=claim):
            return self.client.post("/api/v1/auth/firebase/", payload, format="json")

    def _otp_verify(self, phone: str, gym: str | None = None):
        """Run the real OTP request+verify flow and return the verify response."""
        payload = {"phone": phone}
        if gym:
            payload["gym"] = gym
        overrides = {"DEBUG": True, "OTP_SENDER": "stub", "OTP_RESEND_COOLDOWN_SECONDS": 0}
        with self.settings(**overrides):
            issued = self.client.post("/api/v1/users/auth/otp/request/", payload, format="json")
            assert issued.status_code == 200, issued.data
            payload["otp"] = issued.data["otp"]
            return self.client.post("/api/v1/users/auth/otp/verify/", payload, format="json")

    def test_first_time_phone_anchors_by_typed_gym_code_over_firebase(self) -> None:
        """THE #87 recovery path: unknown phone + hand-typed gym code (messy
        case/spacing included) resolves, auto-provisions and issues a token —
        no dead end. A non-UUID anchor used to die as a DRF shape error."""
        typed = f" {self.tenant.gym_code.lower()}-"  # " px3ctjy-" style entry
        before = User.objects.count()

        response = self._firebase_login("+919900700001", gym=typed)

        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(pk=response.data["user"]["id"])
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(User.objects.count(), before + 1)  # auto-provisioned once
        self.assertNotIn("app.access", response.data["permissions"])  # entitlement none
        self.assertEqual(response.data["entitlement"]["status"], "none")

    def test_first_time_phone_anchors_by_gym_code_over_otp(self) -> None:
        """The OTP route shares the ladder: request AND verify bind to the
        gym the code names, so the same recovery works pre-token."""
        before = User.objects.count()

        verified = self._otp_verify("9900700002", gym=self.tenant.gym_code)

        self.assertEqual(verified.status_code, 200, verified.data)
        user = User.objects.get(pk=verified.data["user"]["id"])
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(User.objects.count(), before + 1)

    def test_gym_code_anchors_to_its_own_gym_not_the_first(self) -> None:
        """Two gyms: the code of gym B anchors there — never first-tenant-wins."""
        other = provision_tenant(name="Gym B", contact_email="b@local.test", features=FLAG_ON)

        response = self._firebase_login("+919900700003", gym=other.gym_code)

        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(pk=response.data["user"]["id"])
        self.assertEqual(user.tenant, other)

    def test_unknown_gym_code_is_a_plain_400_creating_nothing(self) -> None:
        """A code that matches no gym stays the explicit anchor failure —
        never silently ignored, nothing auto-provisioned."""
        before = User.objects.count()

        response = self._firebase_login("+919900700004", gym="ZZZZZZZ")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["gym"], "Unknown gym.")
        self.assertEqual(User.objects.count(), before)

    def test_blank_gym_value_keeps_the_no_anchor_behavior(self) -> None:
        """An empty string anchor (CharField tolerance) is NO anchor: the
        zero-match reply stays the generic non-enumerating 400."""
        response = self._firebase_login("+919900700005", gym="  ")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Specify your gym", str(response.data))

    def test_registered_phone_with_gym_code_converges_not_duplicates(self) -> None:
        """An existing member typing their gym's code converges to their row —
        the code anchor is a resolution path, not a new-identity path."""
        phone = "+919900700006"
        email = f"{phone.strip('+')}.{self.tenant.uuid}@fitnation.local"
        member = User.objects.create_user(
            email=email,
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone=phone,
        )
        Customer.objects.create(tenant=self.tenant, user=member, name="Mem Ber", phone=phone)

        response = self._firebase_login(phone, gym=self.tenant.gym_code)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["id"], member.pk)


class CustomerConvergenceToleranceTests(APITestCase):
    """ERP customer create/edit converges identities across BOTH phone
    formats (ADR-002 rule 1) — raw payload ↔ E.164 row and back."""

    def setUp(self) -> None:
        """Owner-authed client on a fresh tenant."""
        cache.clear()
        self.tenant = provision_tenant(name="Converge Gym", contact_email="own@local.test", features=FLAG_ON)
        owner = create_owner_user(
            tenant=self.tenant,
            email="own@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Own Er",
        )
        token = AuthToken.objects.create(user=owner, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _seed_member(self, phone: str) -> User:
        """A member forced back to the legacy stored form ``phone``."""
        user = User.objects.create_user(
            email=f"member.{phone.strip('+') or 'none'}.conv@fitnation.local",
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone=phone,
        )
        customer = Customer.objects.create(tenant=self.tenant, user=user, name="Mem Ber", phone=phone)
        force_legacy_phone(user=user, customer=customer, phone=phone)
        return user

    def _post_customer(self, phone: str):
        """POST the ERP customer-create endpoint with a phone-only payload."""
        return self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "Far", "last_name": "Zeen", "phone": phone},
            format="json",
        )

    def test_raw_payload_links_e164_identity(self) -> None:
        """The desk types ``8606806956``; the stored identity is ``+91…`` —
        the payload links it instead of provisioning a second user."""
        member = self._seed_member("+918606806956")
        before = User.objects.count()

        response = self._post_customer("8606806956")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(response.data["user"], member.pk)

    def test_e164_payload_links_raw_stored_identity(self) -> None:
        """And the mirror case: an E.164 payload reaches the legacy raw row."""
        member = self._seed_member("8606806957")
        before = User.objects.count()

        response = self._post_customer("+918606806957")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(response.data["user"], member.pk)

    def test_conflicting_real_email_still_rejects_across_formats(self) -> None:
        """Tolerance never waters down ADR-002: a payload email contradicting
        a REAL-email identity is still ``phone_already_registered`` — even
        when the formats disagree (the #88 tolerance must not widen it)."""
        user = User.objects.create_user(
            email="farzeen@real.test",
            password="x",
            first_name="Far",
            last_name="Zeen",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+918606806958",
        )
        customer = Customer.objects.create(
            tenant=self.tenant, user=user, name="Far Zeen", phone="8606806958", email="farzeen@real.test"
        )
        force_legacy_phone(user=user, customer=customer, phone="8606806958")

        response = self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "Other", "last_name": "Person", "phone": "8606806958", "email": "other@real.test"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["phone"][0].code, "phone_already_registered")

    def test_search_by_raw_phone_finds_normalized_row(self) -> None:
        """The ERP member search stays usable: the stored value keeps the
        national digits as a substring of the E.164 form."""
        Customer.objects.create(tenant=self.tenant, name="Sea Rch", phone="8606806959")

        response = self.client.get("/api/v1/customers/customers/?search=8606806959")

        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual([row["name"] for row in results], ["Sea Rch"])
