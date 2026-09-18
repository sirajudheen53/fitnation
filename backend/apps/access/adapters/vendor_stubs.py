"""Stub adapters for vendors pending native integration (issue #22).

These keep the registry complete for every ``Vendor`` choice so device
registration never fails on adapter lookup. ``test_connection`` reports the
device as offline; data operations raise ``NotImplementedError`` until the
native SDK/API integration lands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.access.adapters.base import BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class VendorStubAdapter(BiometricAdapter):
    """Base stub: connection tests report offline, data ops are unimplemented."""

    vendor_label = "Vendor"

    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """Not implemented for this vendor yet."""
        raise NotImplementedError(
            f"{self.vendor_label} allow-list sync is not implemented yet (issue #22 follow-up)."
        )

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Not implemented for this vendor yet."""
        raise NotImplementedError(
            f"{self.vendor_label} event fetch is not implemented yet (issue #22 follow-up)."
        )

    def test_connection(self, device: BiometricDevice) -> dict:
        """Report the device as offline until a native adapter ships."""
        return {
            "online": False,
            "detail": f"{self.vendor_label} adapter not implemented yet; device treated as offline.",
        }


class HikvisionAdapter(VendorStubAdapter):
    """Stub for Hikvision devices (ISAPI/Ehome integration pending)."""

    vendor_label = "Hikvision"


class ZKTecoAdapter(VendorStubAdapter):
    """Stub for ZKTeco devices (Push SDK/ADMS integration pending)."""

    vendor_label = "ZKTeco"


class EsslAdapter(VendorStubAdapter):
    """Stub for eSSL devices (cloud API integration pending)."""

    vendor_label = "eSSL"


class MatrixAdapter(VendorStubAdapter):
    """Stub for Matrix devices (COSEC API integration pending)."""

    vendor_label = "Matrix"


class SupervisionAdapter(VendorStubAdapter):
    """Stub for Supervision devices (integration pending)."""

    vendor_label = "Supervision"
