"""Django signal receivers for inventory low-stock notifications.

When an :class:`~apps.inventory.models.InventoryItem` is saved and its stock
falls to or below its low-stock threshold (with tracking enabled), a
``low_stock`` :class:`~apps.notifications.models.NotificationLog` is recorded
for the tenant. The receiver is defensive: it swallows exceptions so a
notification failure never breaks the inventory write that triggered it.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="inventory.InventoryItem")
def on_inventory_item_low_stock(
    sender: Any,
    instance: Any,
    created: bool,
    **kwargs: Any,
) -> None:
    """Log a low-stock notification when an inventory item drops below threshold.

    Args:
        sender: The model class that sent the signal.
        instance: The saved ``InventoryItem`` instance.
        created: ``True`` if the instance was newly created.
        kwargs: Additional signal keyword arguments.
    """
    if not instance.is_low_stock:
        return

    try:
        from apps.notifications.models import NotificationLog

        NotificationLog.objects.create(
            tenant=instance.tenant,
            customer=None,
            notification_type=NotificationLog.NotificationType.LOW_STOCK,
            status=NotificationLog.Status.PENDING,
            content=(
                f"Low stock alert: {instance.equipment.name} has "
                f"{instance.stock_quantity} unit(s) remaining "
                f"(threshold: {instance.low_stock_threshold})."
            ),
        )
    except Exception:  # noqa: BLE001 - notifications must never break the workflow
        logger.exception("Failed to record low-stock notification for inventory item %s", instance.pk)
