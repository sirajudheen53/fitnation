"""Equipment & inventory serializers."""

from rest_framework import serializers

from apps.inventory.models import Equipment, InventoryItem, MaintenanceLog


class EquipmentSerializer(serializers.ModelSerializer):
    """Serialize equipment details."""

    class Meta:
        """Serializer metadata."""

        model = Equipment
        fields = [
            "id",
            "uuid",
            "name",
            "description",
            "serial_number",
            "purchase_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "created_at", "updated_at"]


class InventoryItemSerializer(serializers.ModelSerializer):
    """Serialize inventory item details, including the computed low-stock flag."""

    is_low_stock = serializers.BooleanField(read_only=True)
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = InventoryItem
        fields = [
            "id",
            "equipment",
            "equipment_name",
            "stock_quantity",
            "low_stock_threshold",
            "track_inventory",
            "is_low_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_equipment(self, equipment: Equipment) -> Equipment:
        """Ensure the equipment belongs to the request tenant."""
        request = self.context.get("request")
        if request is not None and request.tenant is not None:
            if equipment.tenant_id != request.tenant.id:
                raise serializers.ValidationError(
                    "Equipment does not belong to this tenant.",
                )
        return equipment


class MaintenanceLogSerializer(serializers.ModelSerializer):
    """Serialize maintenance log details."""

    equipment_name = serializers.CharField(source="equipment.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = MaintenanceLog
        fields = [
            "id",
            "equipment",
            "equipment_name",
            "performed_at",
            "description",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_equipment(self, equipment: Equipment) -> Equipment:
        """Ensure the equipment belongs to the request tenant."""
        request = self.context.get("request")
        if request is not None and request.tenant is not None:
            if equipment.tenant_id != request.tenant.id:
                raise serializers.ValidationError(
                    "Equipment does not belong to this tenant.",
                )
        return equipment
