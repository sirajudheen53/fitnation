"""Access domain admin — read-mostly views over the biometrics stack.

Device registry stays editable (ops toggles ``is_active`` here); the
ADMS audit/log tables are strictly read-only from admin so live device
traffic can never be rewritten by hand.
"""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.access.models import AdmsRequestLog, BiometricDevice, PunchLogRaw


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    """Registered biometric devices, newest first, with liveness stamp."""

    list_display = (
        "id",
        "serial_number",
        "tenant",
        "branch",
        "vendor",
        "model",
        "is_active",
        "last_seen_at",
        "created_at",
    )
    list_filter = ("vendor", "connection_type", "is_active")
    search_fields = ("serial_number", "name", "tenant__name")
    ordering = ("-created_at",)


@admin.register(PunchLogRaw)
class PunchLogRawAdmin(admin.ModelAdmin):
    """Raw ADMS punch rows — read-only, newest first."""

    list_display = ("id", "received_at", "device_serial", "tenant", "table_name", "raw_preview")
    list_filter = ("table_name",)
    search_fields = ("device__serial_number", "raw_line")
    ordering = ("-received_at",)

    @admin.display(description="Device SN", ordering="device__serial_number")
    def device_serial(self, obj: PunchLogRaw) -> str:
        """Serial number of the device that pushed the row."""
        return obj.device.serial_number

    @admin.display(description="Raw line (preview)")
    def raw_preview(self, obj: PunchLogRaw) -> str:
        """Truncated raw line — full text stays on the detail page."""
        return obj.raw_line[:80]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: PunchLogRaw | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: PunchLogRaw | None = None) -> bool:
        return False


@admin.register(AdmsRequestLog)
class AdmsRequestLogAdmin(admin.ModelAdmin):
    """Inbound ADMS request audit rows — read-only, newest first."""

    list_display = (
        "id",
        "created_at",
        "path",
        "sn",
        "device_serial",
        "tenant",
        "remote_addr",
        "body_preview",
    )
    search_fields = ("sn", "path", "device__serial_number", "remote_addr")
    ordering = ("-created_at",)

    @admin.display(description="Device", ordering="device")
    def device_serial(self, obj: AdmsRequestLog) -> str:
        """Matched device serial, or a marker for unknown-SN 403 hits."""
        return obj.device.serial_number if obj.device else "(unknown → 403)"

    @admin.display(description="Body (preview)")
    def body_preview(self, obj: AdmsRequestLog) -> str:
        """Truncated request body."""
        return obj.raw_body[:80]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: AdmsRequestLog | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AdmsRequestLog | None = None) -> bool:
        return False
