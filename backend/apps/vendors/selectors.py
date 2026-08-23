"""Vendor read selectors."""

from apps.vendors.models import SubscriptionPlan


def active_subscription_plans() -> list[SubscriptionPlan]:
    """Return all active subscription plans ordered by sort order.

    Returns:
        List of active ``SubscriptionPlan`` instances.
    """
    return list(SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order"))
