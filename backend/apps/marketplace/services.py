"""Product marketplace business logic services."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from apps.marketplace.models import Cart, CartItem, Order, OrderItem
from apps.marketplace.selectors import get_or_create_active_cart

if TYPE_CHECKING:
    from apps.tenants.models import Tenant
    from apps.users.models import User


def add_item_to_cart(
    tenant: Tenant,
    user: User,
    product,
    quantity: int,
) -> CartItem:
    """Add a product to the user's active cart (incrementing if present).

    Args:
        tenant: The tenant owning the cart.
        user: The user who owns the cart.
        product: The product to add.
        quantity: The quantity to add.

    Returns:
        The created or updated ``CartItem``.
    """
    cart = get_or_create_active_cart(tenant=tenant, user=user)

    existing = CartItem.objects.filter(cart=cart, product=product).first()
    if existing:
        existing.quantity += quantity
        existing.save(update_fields=["quantity"])
        return existing

    return CartItem.objects.create(
        tenant=tenant,
        cart=cart,
        product=product,
        quantity=quantity,
        unit_price=product.price,
    )


def clear_cart(tenant: Tenant, user: User) -> None:
    """Remove all items from the user's active cart."""
    cart = get_or_create_active_cart(tenant=tenant, user=user)
    cart.items.all().delete()


def place_order(tenant: Tenant, user: User, shipping_address: str = "", billing_address: str = "") -> Order:
    """Convert the user's active cart into an order.

    Args:
        tenant: The tenant owning the cart and order.
        user: The user placing the order.
        shipping_address: Optional shipping address text.
        billing_address: Optional billing address text.

    Returns:
        The created ``Order``.

    Raises:
        ValueError: If the cart is empty.
    """
    cart = get_or_create_active_cart(tenant=tenant, user=user)
    items = list(cart.items.select_related("product"))

    if not items:
        raise ValueError("Cannot place an order from an empty cart.")

    total = sum((Decimal(item.total_price) for item in items), Decimal("0.00"))

    order = Order.objects.create(
        tenant=tenant,
        user=user,
        total_amount=total,
        shipping_address=shipping_address,
        billing_address=billing_address or shipping_address,
        status=Order.Status.PENDING,
        payment_status=Order.PaymentStatus.PENDING,
    )

    for item in items:
        OrderItem.objects.create(
            tenant=tenant,
            order=order,
            product=item.product,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
        )

    cart.status = Cart.Status.COMPLETED
    cart.items.all().delete()
    cart.save(update_fields=["status", "updated_at"])

    return order
