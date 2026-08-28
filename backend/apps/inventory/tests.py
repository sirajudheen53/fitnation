"""Tests for the inventory app."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.inventory.models import Equipment, InventoryItem, MaintenanceLog
from apps.notifications.models import NotificationLog
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


class EquipmentModelTests(TestCase):
    """Unit tests for the Equipment model."""

    def setUp(self) -> None:
        """Create a tenant for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_equipment_requires_tenant(self) -> None:
        """Saving equipment without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Equipment.objects.create(name="Treadmill")

    def test_equipment_tenant_isolation(self) -> None:
        """Equipment is scoped to its tenant."""
        equipment = Equipment.objects.create(tenant=self.tenant, name="Treadmill")
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            Equipment.objects.for_tenant(self.tenant).first().id,
            equipment.id,
        )
        self.assertEqual(Equipment.objects.for_tenant(other_tenant).count(), 0)

    def test_equipment_str(self) -> None:
        """Equipment string representation is its name."""
        equipment = Equipment.objects.create(tenant=self.tenant, name="Dumbbell")
        self.assertEqual(str(equipment), "Dumbbell")


class InventoryItemStrTests(TestCase):
    """Tests for InventoryItem string representation."""

    def setUp(self) -> None:
        """Create a tenant and equipment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.equipment = Equipment.objects.create(tenant=self.tenant, name="Treadmill")

    def test_inventory_item_str(self) -> None:
        """Inventory item string representation includes equipment and quantity."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=7,
        )
        self.assertEqual(str(item), "Inventory: Treadmill (7)")


class MaintenanceLogStrTests(TestCase):
    """Tests for MaintenanceLog string representation."""

    def setUp(self) -> None:
        """Create a tenant and equipment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.equipment = Equipment.objects.create(tenant=self.tenant, name="Treadmill")

    def test_maintenance_log_str(self) -> None:
        """Maintenance log string representation includes equipment and status."""
        log = MaintenanceLog.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            description="Oil change",
        )
        self.assertEqual(str(log), "Treadmill – scheduled")


class InventoryItemModelTests(TestCase):
    """Unit tests for the InventoryItem model."""

    def setUp(self) -> None:
        """Create a tenant and equipment for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.equipment = Equipment.objects.create(tenant=self.tenant, name="Treadmill")

    def test_inventory_item_requires_tenant(self) -> None:
        """Saving an inventory item without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            InventoryItem.objects.create(equipment=self.equipment, stock_quantity=10)

    def test_is_low_stock_when_below_threshold(self) -> None:
        """An item at or below threshold is flagged low stock."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=3,
            low_stock_threshold=5,
        )
        self.assertTrue(item.is_low_stock)

    def test_is_low_stock_when_equal_to_threshold(self) -> None:
        """An item equal to threshold is flagged low stock."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=5,
            low_stock_threshold=5,
        )
        self.assertTrue(item.is_low_stock)

    def test_not_low_stock_when_above_threshold(self) -> None:
        """An item above threshold is not flagged low stock."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=10,
            low_stock_threshold=5,
        )
        self.assertFalse(item.is_low_stock)

    def test_not_low_stock_when_tracking_disabled(self) -> None:
        """An item with tracking disabled is never low stock."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=0,
            low_stock_threshold=5,
            track_inventory=False,
        )
        self.assertFalse(item.is_low_stock)

    def test_inventory_item_tenant_isolation(self) -> None:
        """Inventory items are scoped to their tenant."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=10,
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            InventoryItem.objects.for_tenant(self.tenant).first().id,
            item.id,
        )
        self.assertEqual(InventoryItem.objects.for_tenant(other_tenant).count(), 0)

    def test_inventory_item_unique_equipment_within_tenant(self) -> None:
        """An equipment can only have one inventory item per tenant."""
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=10,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryItem.objects.create(
                tenant=self.tenant,
                equipment=self.equipment,
                stock_quantity=20,
            )


class MaintenanceLogModelTests(TestCase):
    """Unit tests for the MaintenanceLog model."""

    def setUp(self) -> None:
        """Create a tenant and equipment for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.equipment = Equipment.objects.create(tenant=self.tenant, name="Treadmill")

    def test_maintenance_log_requires_tenant(self) -> None:
        """Saving a maintenance log without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            MaintenanceLog.objects.create(
                equipment=self.equipment,
                description="Oil change",
            )

    def test_maintenance_log_default_status(self) -> None:
        """A maintenance log defaults to scheduled status."""
        log = MaintenanceLog.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            description="Oil change",
        )
        self.assertEqual(log.status, MaintenanceLog.Status.SCHEDULED)

    def test_maintenance_log_tenant_isolation(self) -> None:
        """Maintenance logs are scoped to their tenant."""
        log = MaintenanceLog.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            description="Oil change",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            MaintenanceLog.objects.for_tenant(self.tenant).first().id,
            log.id,
        )
        self.assertEqual(MaintenanceLog.objects.for_tenant(other_tenant).count(), 0)


class InventorySignalTests(TestCase):
    """Tests for the low-stock signal receiver."""

    def setUp(self) -> None:
        """Create a tenant and equipment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.equipment = Equipment.objects.create(tenant=self.tenant, name="Treadmill")

    def test_low_stock_creates_notification_log(self) -> None:
        """Saving a low-stock item records a low_stock notification."""
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=2,
            low_stock_threshold=5,
        )
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.LOW_STOCK,
            ).exists()
        )

    def test_above_threshold_no_notification(self) -> None:
        """Saving an item above threshold does not record a notification."""
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=20,
            low_stock_threshold=5,
        )
        self.assertFalse(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.LOW_STOCK,
            ).exists()
        )

    def test_tracking_disabled_no_notification(self) -> None:
        """Saving an item with tracking disabled does not record a notification."""
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=0,
            low_stock_threshold=5,
            track_inventory=False,
        )
        self.assertFalse(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.LOW_STOCK,
            ).exists()
        )

    def test_stock_drop_triggers_notification_on_update(self) -> None:
        """Reducing stock below threshold on update triggers a notification."""
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=self.equipment,
            stock_quantity=20,
            low_stock_threshold=5,
        )
        self.assertFalse(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.LOW_STOCK,
            ).exists()
        )
        item.stock_quantity = 1
        item.save()
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.LOW_STOCK,
            ).exists()
        )


class InventoryAPITests(APITestCase):
    """Integration tests for inventory endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _create_equipment(self, name: str = "Treadmill") -> Equipment:
        """Create an equipment record for the tenant."""
        return Equipment.objects.create(tenant=self.tenant, name=name)

    def test_list_equipment(self) -> None:
        """Owners can list equipment."""
        self._create_equipment()
        response = self.client.get("/api/v1/inventory/equipment/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_equipment(self) -> None:
        """Owners can create equipment."""
        response = self.client.post(
            "/api/v1/inventory/equipment/",
            {"name": "Rowing Machine", "description": "Cardio equipment"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Rowing Machine")

    def test_retrieve_equipment(self) -> None:
        """Owners can retrieve equipment."""
        equipment = self._create_equipment()
        response = self.client.get(f"/api/v1/inventory/equipment/{equipment.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Treadmill")

    def test_update_equipment(self) -> None:
        """Owners can update equipment."""
        equipment = self._create_equipment()
        response = self.client.patch(
            f"/api/v1/inventory/equipment/{equipment.id}/",
            {"name": "Treadmill Pro"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Treadmill Pro")

    def test_delete_equipment(self) -> None:
        """Owners can delete equipment."""
        equipment = self._create_equipment()
        response = self.client.delete(f"/api/v1/inventory/equipment/{equipment.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Equipment.objects.for_tenant(self.tenant).count(), 0)

    def test_create_inventory_item(self) -> None:
        """Owners can create an inventory item."""
        equipment = self._create_equipment()
        response = self.client.post(
            "/api/v1/inventory/inventory-items/",
            {
                "equipment": equipment.id,
                "stock_quantity": 10,
                "low_stock_threshold": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["stock_quantity"], 10)
        self.assertFalse(response.data["is_low_stock"])

    def test_list_inventory_items(self) -> None:
        """Owners can list inventory items."""
        equipment = self._create_equipment()
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            stock_quantity=10,
        )
        response = self.client.get("/api/v1/inventory/inventory-items/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_low_stock_endpoint(self) -> None:
        """The low-stock endpoint returns only items below threshold."""
        low_equipment = self._create_equipment("Low Stock Item")
        ok_equipment = self._create_equipment("OK Item")
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=low_equipment,
            stock_quantity=2,
            low_stock_threshold=5,
        )
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=ok_equipment,
            stock_quantity=50,
            low_stock_threshold=5,
        )
        response = self.client.get("/api/v1/inventory/inventory-items/low_stock/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["equipment_name"], "Low Stock Item")

    def test_low_stock_endpoint_excludes_untracked(self) -> None:
        """The low-stock endpoint excludes items with tracking disabled."""
        equipment = self._create_equipment("Untracked Item")
        InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            stock_quantity=0,
            low_stock_threshold=5,
            track_inventory=False,
        )
        response = self.client.get("/api/v1/inventory/inventory-items/low_stock/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_maintenance_log(self) -> None:
        """Owners can create a maintenance log."""
        equipment = self._create_equipment()
        response = self.client.post(
            "/api/v1/inventory/maintenance-logs/",
            {
                "equipment": equipment.id,
                "description": "Belt replacement",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "completed")

    def test_list_maintenance_logs(self) -> None:
        """Owners can list maintenance logs."""
        equipment = self._create_equipment()
        MaintenanceLog.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            description="Oil change",
        )
        response = self.client.get("/api/v1/inventory/maintenance-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_equipment_tenant_isolation(self) -> None:
        """Equipment from another tenant is not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_equipment = Equipment.objects.create(tenant=other_tenant, name="Other Treadmill")
        response = self.client.get(f"/api/v1/inventory/equipment/{other_equipment.id}/")
        self.assertEqual(response.status_code, 404)

    def test_inventory_item_tenant_isolation(self) -> None:
        """Inventory items from another tenant are not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_equipment = Equipment.objects.create(tenant=other_tenant, name="Other Treadmill")
        other_item = InventoryItem.objects.create(
            tenant=other_tenant,
            equipment=other_equipment,
            stock_quantity=10,
        )
        response = self.client.get(f"/api/v1/inventory/inventory-items/{other_item.id}/")
        self.assertEqual(response.status_code, 404)

    def test_maintenance_log_tenant_isolation(self) -> None:
        """Maintenance logs from another tenant are not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_equipment = Equipment.objects.create(tenant=other_tenant, name="Other Treadmill")
        other_log = MaintenanceLog.objects.create(
            tenant=other_tenant,
            equipment=other_equipment,
            description="Oil change",
        )
        response = self.client.get(f"/api/v1/inventory/maintenance-logs/{other_log.id}/")
        self.assertEqual(response.status_code, 404)

    def test_inventory_item_cross_tenant_equipment_rejected(self) -> None:
        """Creating an inventory item with another tenant's equipment is rejected."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_equipment = Equipment.objects.create(tenant=other_tenant, name="Other Treadmill")
        response = self.client.post(
            "/api/v1/inventory/inventory-items/",
            {
                "equipment": other_equipment.id,
                "stock_quantity": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_maintenance_log_cross_tenant_equipment_rejected(self) -> None:
        """Creating a maintenance log with another tenant's equipment is rejected."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_equipment = Equipment.objects.create(tenant=other_tenant, name="Other Treadmill")
        response = self.client.post(
            "/api/v1/inventory/maintenance-logs/",
            {
                "equipment": other_equipment.id,
                "description": "Oil change",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_update_inventory_item(self) -> None:
        """Owners can update an inventory item."""
        equipment = self._create_equipment()
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            stock_quantity=10,
        )
        response = self.client.patch(
            f"/api/v1/inventory/inventory-items/{item.id}/",
            {"stock_quantity": 3},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stock_quantity"], 3)
        self.assertTrue(response.data["is_low_stock"])

    def test_delete_inventory_item(self) -> None:
        """Owners can delete an inventory item."""
        equipment = self._create_equipment()
        item = InventoryItem.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            stock_quantity=10,
        )
        response = self.client.delete(f"/api/v1/inventory/inventory-items/{item.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(InventoryItem.objects.for_tenant(self.tenant).count(), 0)

    def test_update_maintenance_log(self) -> None:
        """Owners can update a maintenance log."""
        equipment = self._create_equipment()
        log = MaintenanceLog.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            description="Oil change",
        )
        response = self.client.patch(
            f"/api/v1/inventory/maintenance-logs/{log.id}/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")

    def test_delete_maintenance_log(self) -> None:
        """Owners can delete a maintenance log."""
        equipment = self._create_equipment()
        log = MaintenanceLog.objects.create(
            tenant=self.tenant,
            equipment=equipment,
            description="Oil change",
        )
        response = self.client.delete(f"/api/v1/inventory/maintenance-logs/{log.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MaintenanceLog.objects.for_tenant(self.tenant).count(), 0)
