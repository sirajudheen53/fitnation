"""Access app tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.test import TestCase

from apps.access.models import AccessLog, AccessOverride, BiometricDevice
from apps.access.selectors import get_customer_access_state
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.models import Tenant
from apps.users.models import User


class AccessTestBase(TestCase):
    """Shared fixture for access app tests."""

    def setUp(self) -> None:
        """Set up test data with proper user FK for customer."""
        self.tenant = Tenant.objects.create(name="Test Gym", contact_email="gym@test.com")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        self.user = User.objects.create_user(
            email="owner@test.com",
            password="test123",
            first_name="Gym",
            last_name="Owner",
            role="owner",
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=self.user,
            name="John Doe",
            phone="+919999999999",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="hikvision",
            model="DS-K1T321MFWX",
            serial_number="SN123456",
            name="Main Entrance",
        )


class DeviceRegistryTest(AccessTestBase):
    """Test biometric device registration and scoping."""

    def test_device_creation(self) -> None:
        """Create a biometric device."""
        device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="hikvision",
            model="DS-K1T321MFWX",
            serial_number="SN789",
            name="Second Entrance",
        )
        assert device.pk is not None
        assert device.tenant == self.tenant

    def test_device_unique_serial_per_branch(self) -> None:
        """Enforce unique serial per branch."""
        with self.assertRaises(Exception):
            BiometricDevice.objects.create(
                tenant=self.tenant,
                branch=self.branch,
                vendor="zkteco",
                model="MB10",
                serial_number="SN123456",
                name="Second Device",
            )


class AccessOverrideTest(AccessTestBase):
    """Test access override logic."""

    def test_owner_override_grants_access(self) -> None:
        """Owner override can grant access to members."""
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=True,
            reason="grace_period",
            created_by=self.user,
        )
        result = get_customer_access_state(customer=self.customer, device=self.device)
        assert result["allowed"] is True
        assert result["source"] == "override"

    def test_owner_override_denies_access(self) -> None:
        """Owner override can revoke access from members."""
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=False,
            reason="violation",
            created_by=self.user,
        )
        result = get_customer_access_state(customer=self.customer, device=self.device)
        assert result["allowed"] is False
        assert result["source"] == "override"

    def test_expired_override_ignored(self) -> None:
        """Expired overrides are not applied."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=True,
            reason="grace_period",
            expires_at=past,
        )
        result = get_customer_access_state(customer=self.customer, device=self.device)
        # Should fall through to plan check
        assert result["source"] != "override"


class AccessLogTest(AccessTestBase):
    """Test access event logging."""

    def test_record_entry_event(self) -> None:
        """Log an entry event."""
        log = AccessLog.objects.create(
            tenant=self.tenant,
            device=self.device,
            customer=self.customer,
            device_user_id="D001",
            credential_type="fingerprint",
            event_type="entry",
            event_timestamp=datetime.now(timezone.utc),
        )
        assert log.pk is not None
        assert log.tenant == self.tenant
