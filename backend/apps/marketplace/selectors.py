"""Product marketplace read/selector services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.marketplace.models import Cart

if TYPE_CHECKING:
    from apps.tenants.models import Tenant
    from apps.users.models import User


def get_or_create_active_cart(tenant: Tenant, user: User) -> Cart:
    """Return the user's active cart, creating one if none exists.

    Args:
        tenant: The tenant owning the cart.
        user: The user who owns the cart.

    Returns:
        The active ``Cart`` instance (created if necessary).
    """
    cart = Cart.objects.for_tenant(tenant).filter(user=user, status=Cart.Status.ACTIVE).first()
    if cart is None:
        cart = Cart.objects.create(tenant=tenant, user=user)
    return cart
