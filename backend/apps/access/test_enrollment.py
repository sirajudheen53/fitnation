"""Phase-2 enrollment tests: canonical device_user_id + idempotent enroll.

Covers owner decisions locked 2026-10-22: one canonical device_user_id
per customer per tenant, reused on every device, plus the front-desk API
surface (list / enroll / deactivate) under /api/v1/access/.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import localdate
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.access.models import BiometricCredential, BiometricDevice, DeviceCommandQueue
from apps.access.propagation import (
    DEFAULT_COOL_OFF_DAYS,
    biometric_access_valid_until,
    cool_off_days_for,
    is_membership_in_cool_off,
    propagate_enrollment,
)
from apps.access.services import enroll_credential, resolve_device_user_id
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token


class EnrollmentTestBase(TestCase):
    """Shared fixtures: tenant, branch, customer, ADMS-family device."""

    def setUp(self) -> None:
        """Create tenant, branch, customer, and a zkteco device."""
        self.tenant = provision_tenant(name="Enroll Gym", contact_email="owner@enroll.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="cust@enroll.test",
            password="testpass",
            first_name="John",
            last_name="Doe",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="John Doe",
            phone="+919999000001",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="ENROLL-DEV-1",
            name="Main Entrance",
            connection_type="webhook",
        )

    def _other_device(self, serial: str = "ENROLL-DEV-2", name: str = "Side Door") -> BiometricDevice:
        """A second device in the same branch."""
        return BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number=serial,
            name=name,
            connection_type="webhook",
        )

    def _other_customer(self, email: str, name: str) -> Customer:
        """A second customer in the same tenant."""
        user = User.objects.create_user(
            email=email,
            password="testpass",
            first_name=name.split()[0],
            last_name=name.split()[-1],
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        return Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name=name,
            phone="+919999000002",
        )

    def _membership(self, customer: Customer, *, ends_in_days: int = 25) -> Membership:
        """Create an active membership (negative = already ended)."""
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Silver Monthly",
            price=Decimal("500.00"),
            duration_days=30,
        )
        today = localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=customer,
            plan=plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=ends_in_days),
        )


class CanonicalDeviceUserIdTest(EnrollmentTestBase):
    """resolve_device_user_id — one canonical id per customer per tenant."""

    def test_first_customer_gets_integer_one(self) -> None:
        """A customer with no credentials is allocated '1'."""
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "1"

    def test_existing_credential_id_is_reused(self) -> None:
        """The id of the customer's active credential is the canonical id."""
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="7",
        )
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "7"

    def test_allocation_is_tenant_wide_max_plus_one(self) -> None:
        """New customers get tenant-wide max integer id + 1, gaps skipped."""
        other = self._other_customer("other@enroll.test", "Jane Roe")
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=other,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="41",
        )
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "42"

    def test_non_integer_ids_do_not_break_allocation(self) -> None:
        """Legacy alphanumeric ids are ignored by the allocator."""
        other = self._other_customer("other@enroll.test", "Jane Roe")
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=other,
            device=self.device,
            credential_type="card",
            device_user_id="CARD-009",
        )
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "1"

    def test_allocation_scoped_to_tenant(self) -> None:
        """Another tenant's ids never influence this tenant's allocation."""
        other_tenant = provision_tenant(name="Rival Gym", contact_email="owner@rival.test")
        other_branch = Branch.objects.create(tenant=other_tenant, name="Rival Branch", branch_type="gym")
        other_device = BiometricDevice.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="RIVAL-DEV-1",
            name="Rival Entrance",
        )
        rival_user = User.objects.create_user(
            email="rival@enroll.test",
            password="testpass",
            first_name="Rival",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        rival = Customer.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            user=rival_user,
            name="Rival Member",
            phone="+919999000009",
        )
        BiometricCredential.objects.create(
            tenant=other_tenant,
            customer=rival,
            device=other_device,
            credential_type="fingerprint",
            device_user_id="999",
        )
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "1"

    def test_inactive_credential_id_not_reused_as_canonical(self) -> None:
        """Only active credentials carry the canonical id; a fresh id is allocated."""
        other = self._other_customer("other@enroll.test", "Jane Roe")
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=other,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="41",
        )
        deactivated = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="42",
            is_active=False,
        )
        # The customer's only credential is inactive → allocate past tenant max.
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "43"
        deactivated.is_active = True
        deactivated.save(update_fields=["is_active", "updated_at"])
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "42"


class IdempotentEnrollTest(EnrollmentTestBase):
    """enroll_credential — upsert semantics per (customer, device)."""

    def test_enroll_creates_row_with_canonical_id(self) -> None:
        """A plain enroll allocates the canonical id server-side."""
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert credential.device_user_id == "1"
        assert credential.is_active is True

    def test_reenroll_updates_instead_of_erroring(self) -> None:
        """Re-enrolling the same (customer, device) refreshes the row."""
        first = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        again = enroll_credential(
            tenant=self.tenant, device=self.device, customer=self.customer, credential_type="card"
        )
        assert again.pk == first.pk
        assert again.credential_type == "card"
        assert BiometricCredential.objects.filter(customer=self.customer, device=self.device).count() == 1

    def test_reenroll_after_deactivate_reactivates(self) -> None:
        """A deactivated credential comes back active on re-enroll."""
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        credential.is_active = False
        credential.save(update_fields=["is_active", "updated_at"])
        again = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert again.pk == credential.pk
        assert again.is_active is True

    def test_same_customer_second_device_reuses_canonical_id(self) -> None:
        """The canonical id follows the customer onto every new device."""
        first = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        second_device = self._other_device()
        second = enroll_credential(tenant=self.tenant, device=second_device, customer=self.customer)
        assert second.device_user_id == first.device_user_id == "1"

    def test_explicit_device_user_id_is_honored(self) -> None:
        """An explicit id still wins over allocation (legacy callers)."""
        credential = enroll_credential(
            tenant=self.tenant,
            device=self.device,
            customer=self.customer,
            device_user_id="777",
        )
        assert credential.device_user_id == "777"

    def test_explicit_id_conflict_with_other_customer_rejected(self) -> None:
        """An id held by a different customer on the device raises."""
        other = self._other_customer("other@enroll.test", "Jane Roe")
        enroll_credential(tenant=self.tenant, device=self.device, customer=other, device_user_id="5")
        with self.assertRaises(ValidationError):
            enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer, device_user_id="5")

    def test_canonical_id_repoint_onto_taken_slot_rejected(self) -> None:
        """Re-enroll keeps the row when the canonical id slot is occupied."""
        other = self._other_customer("other@enroll.test", "Jane Roe")
        enroll_credential(tenant=self.tenant, device=self.device, customer=other, device_user_id="1")
        legacy = enroll_credential(
            tenant=self.tenant,
            device=self.device,
            customer=self.customer,
            device_user_id="STAFF-9",
        )
        # Canonical for this customer resolves to "1" (free tenant-wide), but
        # another customer holds it on this device — the row stays usable.
        again = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert again.pk == legacy.pk
        assert again.device_user_id == "STAFF-9"

    def test_invalid_credential_type_rejected(self) -> None:
        """Unknown credential types are a validation error, not a crash."""
        with self.assertRaises(ValidationError):
            enroll_credential(
                tenant=self.tenant,
                device=self.device,
                customer=self.customer,
                credential_type="retina",
            )


class CoolOffHelperTest(EnrollmentTestBase):
    """Cool-off math: end_date + N days, tenant-overridable."""

    def test_default_cool_off_is_three_days(self) -> None:
        """The locked default is 3 days."""
        assert cool_off_days_for(self.tenant) == DEFAULT_COOL_OFF_DAYS == 3

    def test_tenant_feature_override(self) -> None:
        """tenant.features['biometric_cool_off_days'] overrides the default."""
        self.tenant.features = {"biometric_cool_off_days": 7}
        assert cool_off_days_for(self.tenant) == 7
        self.tenant.features = {"biometric_cool_off_days": "bogus"}
        assert cool_off_days_for(self.tenant) == DEFAULT_COOL_OFF_DAYS

    def test_valid_until_adds_cool_off(self) -> None:
        """valid_until = end_date + cool_off."""
        membership = self._membership(self.customer, ends_in_days=25)
        assert biometric_access_valid_until(membership, self.tenant) == membership.end_date + timedelta(days=3)

    def test_cool_off_boundary_day3_vs_day4(self) -> None:
        """Access holds through end+3 and is gone on end+4."""
        membership = self._membership(self.customer)
        end = membership.end_date
        assert is_membership_in_cool_off(membership, self.tenant, today=end + timedelta(days=3)) is True
        assert is_membership_in_cool_off(membership, self.tenant, today=end + timedelta(days=4)) is False

    def test_active_membership_is_in_cool_off(self) -> None:
        """A live membership trivially passes the gate."""
        membership = self._membership(self.customer)
        assert is_membership_in_cool_off(membership, self.tenant) is True

    def test_cancelled_membership_never_in_cool_off(self) -> None:
        """Cancellation revokes immediately — no cool-off grace."""
        membership = self._membership(self.customer)
        membership.status = "cancelled"
        membership.save(update_fields=["status"])
        assert is_membership_in_cool_off(membership, self.tenant) is False
        assert is_membership_in_cool_off(None, self.tenant) is False

    def test_overridden_cool_off_respected_in_boundary(self) -> None:
        """A tenant-specific cool-off length moves the boundary."""
        self.tenant.features = {"biometric_cool_off_days": 7}
        membership = self._membership(self.customer)
        end = membership.end_date
        assert is_membership_in_cool_off(membership, self.tenant, today=end + timedelta(days=7)) is True
        assert is_membership_in_cool_off(membership, self.tenant, today=end + timedelta(days=8)) is False


class EnrollmentPropagationGateTest(EnrollmentTestBase):
    """propagate_enrollment — device command only with a live membership."""

    def test_enroll_with_active_membership_queues_userinfo_update(self) -> None:
        """An active membership queues the metadata push for the device."""
        self._membership(self.customer)
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        queued = propagate_enrollment(credential)
        assert queued is not None
        assert queued.command == "DATA UPDATE USERINFO"
        assert queued.device_id == self.device.pk
        assert queued.payload["pin"] == credential.device_user_id
        assert queued.payload["name"] == "John Doe"
        assert queued.payload["privilege"] == 0
        assert queued.payload["valid_date"]

    def test_enroll_without_membership_queues_nothing(self) -> None:
        """No live membership: credential exists, device knows nothing."""
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert propagate_enrollment(credential) is None
        assert DeviceCommandQueue.objects.count() == 0

    def test_enroll_inside_cool_off_queues_update(self) -> None:
        """Expired-but-in-cool-off memberships still push the user."""
        self._membership(self.customer, ends_in_days=-2)
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert propagate_enrollment(credential) is not None

    def test_enroll_past_cool_off_queues_nothing(self) -> None:
        """Expired past the cool-off: no device command."""
        self._membership(self.customer, ends_in_days=-4)
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert propagate_enrollment(credential) is None

    def test_cancelled_membership_queues_nothing(self) -> None:
        """Cancelled memberships push nothing on enroll."""
        membership = self._membership(self.customer)
        membership.status = "cancelled"
        membership.save(update_fields=["status"])
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        assert propagate_enrollment(credential) is None


class EnrollAPITests(APITestCase):
    """Front-desk enroll / list / deactivate endpoints (owner token)."""

    def setUp(self) -> None:
        """Create tenant, owner token, member with plan, device."""
        self.tenant = provision_tenant(name="API Gym", contact_email="owner@api.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@api.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="API Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Gold Monthly",
            price=Decimal("900.00"),
            duration_days=30,
        )
        user = User.objects.create_user(
            email="member@api.test",
            password="testpass",
            first_name="Mia",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Mia Member",
            email="member@api.test",
            phone="+916000000001",
        )
        today = localdate()
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="API-DEV-1",
            name="Main Entrance",
            connection_type="webhook",
        )
        self.enroll_url = "/api/v1/access/devices/enroll/"
        self.credentials_url = "/api/v1/access/credentials/"

    def test_enroll_without_device_user_id_returns_canonical_id(self) -> None:
        """POST enroll without an id allocates the canonical id server-side."""
        response = self.client.post(
            self.enroll_url,
            {"customer": self.customer.pk, "device": self.device.pk, "credential_type": "fingerprint"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["credential"]["device_user_id"], "1")
        assert DeviceCommandQueue.objects.filter(command="DATA UPDATE USERINFO").count() == 1

    def test_enroll_is_idempotent_and_returns_same_id(self) -> None:
        """Re-enrolling via the API refreshes the row, not an error."""
        payload = {"customer": self.customer.pk, "device": self.device.pk, "credential_type": "fingerprint"}
        first = self.client.post(self.enroll_url, payload, format="json")
        payload["credential_type"] = "card"
        second = self.client.post(self.enroll_url, payload, format="json")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["credential"]["id"], first.data["credential"]["id"])
        self.assertEqual(second.data["credential"]["device_user_id"], "1")
        assert BiometricCredential.objects.filter(customer=self.customer).count() == 1

    def test_credentials_list_filters_by_customer(self) -> None:
        """GET credentials?customer= lists that customer's enrollments."""
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        response = self.client.get(f"{self.credentials_url}?customer={self.customer.pk}")
        self.assertEqual(response.status_code, 200)
        results = (
            response.data["results"]
            if isinstance(response.data, dict) and "results" in response.data
            else (response.data)
        )
        assert [row["id"] for row in results] == [credential.pk]
        assert results[0]["device_user_id"] == "1"

    def test_deactivate_endpoint_disables_credential(self) -> None:
        """POST deactivate flips is_active and returns the row."""
        credential = enroll_credential(tenant=self.tenant, device=self.device, customer=self.customer)
        response = self.client.post(f"{self.credentials_url}{credential.pk}/deactivate/")
        self.assertEqual(response.status_code, 200)
        assert response.data["is_active"] is False
        credential.refresh_from_db()
        assert credential.is_active is False
        # Resolving the canonical id now allocates fresh (row inactive).
        assert resolve_device_user_id(tenant=self.tenant, customer=self.customer) == "2"
