"""Access app domain services — all write operations."""

from __future__ import annotations

from typing import TYPE_CHECKING


from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
    ConnectionType,
    CredentialType,
)

if TYPE_CHECKING:
    from apps.branches.models import Branch
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant
    from apps.users.models import User


def create_device(
    *,
    tenant: Tenant,
    branch: Branch,
    vendor: str,
    model: str,
    serial_number: str,
    name: str,
    connection_type: str = ConnectionType.WEBHOOK,
    api_endpoint: str = "",
    api_key: str = "",
) -> BiometricDevice:
    """Register a new biometric device for a branch."""
    return BiometricDevice.objects.create(
        tenant=tenant,
        branch=branch,
        vendor=vendor,
        model=model,
        serial_number=serial_number,
        name=name,
        connection_type=connection_type,
        api_endpoint=api_endpoint,
        api_key=api_key,
    )


def enroll_credential(
    *,
    tenant: Tenant,
    device: BiometricDevice,
    customer: Customer,
    credential_type: str = CredentialType.FINGERPRINT,
    device_user_id: str,
) -> BiometricCredential:
    """Enroll a customer credential on a device."""
    return BiometricCredential.objects.create(
        tenant=tenant,
        customer=customer,
        device=device,
        credential_type=credential_type,
        device_user_id=device_user_id,
    )


def create_override(
    *,
    tenant: Tenant,
    customer: Customer,
    device: BiometricDevice,
    allow_access: bool,
    reason: str,
    created_by: User | None = None,
    reason_notes: str = "",
    expires_at: str | None = None,
) -> AccessOverride:
    """Create an owner override for a customer's device access."""
    return AccessOverride.objects.create(
        tenant=tenant,
        customer=customer,
        device=device,
        allow_access=allow_access,
        reason=reason,
        reason_notes=reason_notes,
        expires_at=expires_at,
        created_by=created_by,
    )


def record_event(
    *,
    device: BiometricDevice,
    customer: Customer | None,
    credential_type: str,
    device_user_id: str,
    event_type: str,
    event_timestamp: str,
    raw_payload: dict | None = None,
) -> AccessLog:
    """Record an access event from a biometric device."""
    return AccessLog.objects.create(
        tenant=device.tenant,
        device=device,
        customer=customer,
        device_user_id=device_user_id,
        credential_type=credential_type,
        event_type=event_type,
        event_timestamp=event_timestamp,
        raw_payload=raw_payload or {},
    )
