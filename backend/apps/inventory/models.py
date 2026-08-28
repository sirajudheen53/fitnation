"""Equipment & inventory models, tenant-scoped."""

import uuid as uuid_lib

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin


class Equipment(TenantModelMixin):
    """Physical equipment owned by a gym (e.g., treadmill, dumbbell)."""

    uuid = models.UUIDField(
        default=uuid_lib.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Equipment model metadata."""

        db_table = "equipment"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "uuid"], name="uq_equipment_tenant_uuid"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class InventoryItem(TenantModelMixin):
    """Stock tracking for a piece of equipment."""

    equipment = models.OneToOneField(
        Equipment, on_delete=models.CASCADE, related_name="inventory_item"
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    track_inventory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """InventoryItem model metadata."""

        db_table = "inventory_items"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "equipment"], name="uq_inventory_tenant_equipment"
            ),
        ]

    @property
    def is_low_stock(self) -> bool:
        """Return ``True`` when ``stock_quantity`` ≤ ``low_stock_threshold`` and tracking is enabled."""
        if not self.track_inventory:
            return False
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self) -> str:
        return f"Inventory: {self.equipment.name} ({self.stock_quantity})"


class MaintenanceLog(TenantModelMixin):
    """Log of maintenance activities performed on equipment."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name="maintenance_logs"
    )
    performed_at = models.DateTimeField(default=timezone.now)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """MaintenanceLog model metadata."""

        db_table = "maintenance_logs"
        ordering = ["-performed_at"]

    def __str__(self) -> str:
        return f"{self.equipment.name} – {self.status}"
