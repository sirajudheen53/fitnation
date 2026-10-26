"""Account-deletion tests (spec §8 task B8): anonymization, session teardown,
identity plumbing purge, health-data erasure, cross-tenant isolation, and the
retained-but-non-identifying business records (Google Play deletion mandate).
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord
from apps.customers.models import BodyMeasurement, Customer, HealthProfile
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import DeviceToken
from apps.payments.models import Invoice, Payment
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, EmailVerificationToken, OtpCode, User

PHONE = "+919900055001"
PHONE2 = "+919900055002"


class DeleteAccountTestBase(APITestCase):
    """One member's full paper trail across two tenants of the same phone."""

    def setUp(self) -> None:
        """Tenant A (the caller's gym), tenant B (same phone, still a member)."""
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test")
        self.other_tenant = provision_tenant(name="Iron Yard", contact_email="iron@local.test")
        self.owner = User.objects.create_user(
            email="owner@hash.local",
            password="F1tNati0n!",
            first_name="Own",
            last_name="Er",
            role=User.Role.GYM_OWNER,
            tenant=self.tenant,
            is_owner=True,
        )
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly Unlimited",
            price=2500,
            duration_days=30,
        )
        self.other_plan = MembershipPlan.objects.create(
            tenant=self.other_tenant,
            name="Iron Monthly",
            price=1900,
            duration_days=30,
        )
        self.user = self.make_customer(PHONE, self.tenant)
        self.other_user = self.make_customer(PHONE, self.other_tenant)
        self.peer = self.make_customer(PHONE2, self.tenant)
        self.today = timezone.localdate()

    def make_customer(self, phone: str, tenant, email: str | None = None) -> User:
        """Create a customer user keyed to the phone (tenant-scoped email)."""
        user = User.objects.create_user(
            email=email or f"{phone.replace('+', '')}.{tenant.uuid}@fitnation.local",
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=User.Role.CUSTOMER,
            tenant=tenant,
            phone=phone,
        )
        EmailVerificationToken.create_token(user)
        return user

    def give_paper_trail(self, user: User, *, tenant) -> Customer:
        """Membership, payment, invoice, attendance, health + device data."""
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        tenant_pk = tenant.pk
        tenant_plan = self.plan if tenant == self.tenant else self.other_plan
        customer = Customer.objects.create(
            tenant=tenant,
            user=user,
            name=f"Person {phone_label(user.phone)}",
            email=user.email,
            phone=user.phone,
            date_of_birth=self.today - timedelta(days=9000),
            gender=Customer.Gender.MALE,
            emergency_contact_name="Spouse Ber",
            emergency_contact_phone="+918000000000",
            address_street="12 MG Road",
            address_city="Bengaluru",
            address_state="KA",
            address_postal_code="560001",
            notes="Prefers evening slots",
        )
        membership = Membership.objects.create(
            tenant=tenant,
            customer=customer,
            plan=tenant_plan,
            start_date=self.today - timedelta(days=10),
            end_date=self.today + timedelta(days=20),
        )
        payment = Payment.objects.create(
            tenant=tenant,
            customer=customer,
            membership=membership,
            amount=2500,
            payment_method=Payment.PaymentMethod.UPI,
        )
        Invoice.objects.create(
            tenant=tenant,
            customer=customer,
            payment=payment,
            invoice_number=f"INV-{tenant_pk}-{customer.pk}",
            subtotal=2500,
            total=2500,
        )
        AttendanceRecord.objects.create(tenant=tenant, customer=customer, check_in_time=timezone.now())
        BodyMeasurement.objects.create(
            tenant=tenant,
            customer=customer,
            weight_kg=80.5,
        )
        self.tokens(customer, tenant)
        return customer

    def tokens(self, customer: Customer, tenant) -> None:
        """OTP row + push token for the member (purge candidates in tenant)."""
        OtpCode.objects.create(
            phone=customer.phone,
            tenant=tenant,
            code_hash="x" * 64,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        DeviceToken.objects.create(
            tenant=tenant,
            user=customer.user,
            customer=customer,
            token=f"fcm-{customer.pk}-{tenant.pk}",
        )

    def auth(self, user: User) -> None:
        """Authenticate the test client as ``user``."""
        token = AuthToken.objects.create(user=user, tenant=user.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token

    def delete_account(self) -> None:
        """Call the deletion endpoint for the tenant-A member."""
        response = self.client.post(
            "/api/v1/users/auth/delete-account/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response


def phone_label(phone: str) -> str:
    """Last four digits — only for building test fixture names."""
    return phone[-4:]


class DeleteAccountTests(DeleteAccountTestBase):
    """The full delete flow for the tenant-A member (``+919900055001``)."""

    def setUp(self) -> None:
        """Give the A-member their complete paper trail, then authenticate."""
        super().setUp()
        self.customer = self.give_paper_trail(self.user, tenant=self.tenant)
        HealthProfile.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            height_cm=180,
            weight_kg=80.5,
        )
        self.auth(self.user)

    def test_anonymizes_user_data(self) -> None:
        """The user row survives but carries no personal values any more."""
        response = self.delete_account()
        self.assertEqual(response.data["message"], "Account deleted")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Deleted")
        self.assertEqual(self.user.last_name, "Member")
        self.assertNotEqual(self.user.email, f"{PHONE.replace('+', '')}@fitnation.local")
        self.assertTrue(self.user.email.startswith("deleted-"))
        self.assertNotIn(PHONE.replace("+", ""), self.user.email)

        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(self.user.phone, "")

    def test_deactivates_and_scrubs_customer_profile(self) -> None:
        """The customer row stays (for the records) but is inactive + scrubbed."""
        customer_pk = self.customer.pk
        self.delete_account()

        customer = Customer.objects.filter(user=self.user, pk=customer_pk).first()
        self.assertIsNotNone(customer)
        self.assertFalse(customer.is_active)
        self.assertEqual(customer.status, Customer.Status.INACTIVE)
        self.assertEqual(customer.name, "Deleted user")  # issue #81 label
        self.assertIsNotNone(customer.deleted_at)  # issue #81 marker
        self.assertEqual(customer.phone, "")
        self.assertIsNone(customer.email)
        self.assertIsNone(customer.date_of_birth)
        self.assertEqual(customer.gender, Customer.Gender.PREFER_NOT_TO_SAY)
        self.assertIsNone(customer.emergency_contact_name)
        self.assertEqual(customer.address_street, "")
        self.assertEqual(customer.notes, "")

    def test_health_data_is_erased(self) -> None:
        """Health records are deleted, not anonymised — the Play mandate."""
        self.delete_account()
        self.assertFalse(HealthProfile.objects.filter(customer=self.customer).exists())
        self.assertFalse(BodyMeasurement.objects.filter(customer=self.customer).exists())

    def test_all_session_tokens_are_dead(self) -> None:
        """Every token dies; a replay of the old credentials is rejected."""
        token = self.auth(self.user)
        self.assertTrue(AuthToken.objects.filter(user=self.user, is_active=True).exists())
        # A second live token on another "device".
        AuthToken.objects.create(user=self.user, tenant=self.tenant, device_type="android")
        self.delete_account()

        self.assertFalse(AuthToken.objects.filter(user=self.user, is_active=True).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/v1/users/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_otp_rows_purged_in_tenant_only(self) -> None:
        """The member's OTPs die at gym A; gym B's identical phone keeps its."""
        self.give_paper_trail(self.other_user, tenant=self.other_tenant)
        self.delete_account()
        self.assertFalse(OtpCode.objects.filter(tenant=self.tenant, phone=PHONE).exists())
        self.assertTrue(OtpCode.objects.filter(tenant=self.other_tenant, phone=PHONE).exists())

    def test_device_tokens_purged_in_tenant_only(self) -> None:
        """Push bindings die at gym A; gym B's registration survives."""
        self.give_paper_trail(self.other_user, tenant=self.other_tenant)
        self.delete_account()
        self.assertFalse(DeviceToken.objects.filter(tenant=self.tenant, user=self.user).exists())
        self.assertTrue(DeviceToken.objects.filter(tenant=self.other_tenant, user=self.other_user).exists())

    def test_verification_tokens_purged(self) -> None:
        """Email verification tokens carry identity anchors; they go too."""
        self.delete_account()
        self.assertFalse(EmailVerificationToken.objects.filter(user=self.user).exists())

    def test_business_records_retained_but_non_identifying(self) -> None:
        """Membership/payment/invoice/attendance survive — un-linked a person."""
        customer_pk = self.customer.pk
        self.delete_account()

        customer = Customer.objects.get(pk=customer_pk)
        self.assertTrue(Membership.objects.for_tenant(self.tenant).filter(customer=customer).exists())
        self.assertTrue(Payment.objects.for_tenant(self.tenant).filter(customer=customer).exists())
        self.assertTrue(Invoice.objects.for_tenant(self.tenant).filter(customer=customer).exists())
        self.assertTrue(AttendanceRecord.objects.for_tenant(self.tenant).filter(customer=customer).exists())
        self.assertEqual(customer.name, "Deleted user")  # issue #81 label
        self.assertFalse(Customer.objects.filter(tenant=self.tenant, phone=PHONE).exists())

    def test_same_phone_at_another_tenant_is_untouched(self) -> None:
        """Gym B's member of the same human keeps identity + live membership."""
        self.give_paper_trail(self.other_user, tenant=self.other_tenant)
        other_before = {
            "email": self.other_user.email,
            "phone": self.other_user.phone,
        }
        self.delete_account()

        self.other_user.refresh_from_db()
        self.assertEqual(self.other_user.email, other_before["email"])
        self.assertEqual(self.other_user.phone, other_before["phone"])
        self.assertTrue(self.other_user.is_active)
        other_customer = Customer.objects.get(user=self.other_user)
        self.assertTrue(other_customer.is_active)
        self.assertNotEqual(other_customer.name, "Deleted user")

    def test_peer_in_same_tenant_is_untouched(self) -> None:
        """Another member at the same gym is neither deleted nor logged out."""
        self.give_paper_trail(self.peer, tenant=self.tenant)
        self.delete_account()

        self.peer.refresh_from_db()
        self.assertTrue(self.peer.is_active)
        self.assertTrue(self.peer.email.endswith("@fitnation.local"))
        peer_customer = Customer.objects.get(user=self.peer)
        self.assertTrue(peer_customer.is_active)
        self.assertEqual(peer_customer.phone, PHONE2)
        self.assertTrue(OtpCode.objects.filter(tenant=self.tenant, phone=PHONE2).exists())

    def test_staff_account_rejected(self) -> None:
        """Staff cannot use this endpoint — own or otherwise."""
        self.auth(self.owner)
        response = self.client.post("/api/v1/users/auth/delete-account/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)
        self.assertNotIn("deleted-", self.owner.email)
        # …and no deletion happened at all.
        self.assertTrue(Customer.objects.filter(user=self.user).first().is_active)

    def test_unauthenticated_rejected(self) -> None:
        """Anonymous calls are 401."""
        self.client.credentials()
        response = self.client.post("/api/v1/users/auth/delete-account/", {})
        self.assertEqual(response.status_code, 401)

    def test_customer_without_profile_still_anonymized(self) -> None:
        """A phone-keyed identity with no customer profile is scrubbed too."""
        orphan = self.make_customer("+919900055003", self.tenant)
        self.auth(orphan)
        response = self.delete_account()
        self.assertEqual(response.status_code, 200)
        orphan.refresh_from_db()
        self.assertFalse(orphan.is_active)
        self.assertEqual(orphan.phone, "")
