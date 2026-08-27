"""Product marketplace models."""

import uuid as uuid_lib

from django.db import models

from apps.tenants.models import TenantModelMixin
from apps.users.models import User


class ProductCategory(TenantModelMixin):
    """A tenant-scoped category grouping products (e.g. Supplements, Equipment)."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """ProductCategory model metadata."""

        db_table = "product_categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="uq_product_category_tenant_slug",
            ),
        ]

    def __str__(self) -> str:
        """Return category label."""
        return f"{self.name}"


class Product(TenantModelMixin):
    """A tenant-scoped product sold in the marketplace."""

    class Status(models.TextChoices):
        """Lifecycle status of a product."""

        ACTIVE = "active", "Active"
        DRAFT = "draft", "Draft"
        ARCHIVED = "archived", "Archived"

    uuid = models.UUIDField(
        default=uuid_lib.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    sku = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_digital = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Product model metadata."""

        db_table = "products"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="uq_product_tenant_slug",
            ),
            models.UniqueConstraint(
                fields=["tenant", "sku"],
                name="uq_product_tenant_sku",
            ),
        ]

    def __str__(self) -> str:
        """Return product label."""
        return f"{self.name}"

    @property
    def is_low_stock(self) -> bool:
        """Return whether the tracked inventory is at or below the low-stock threshold."""
        inventory = getattr(self, "inventory", None)
        if inventory is None or not inventory.track_inventory or inventory.low_stock_threshold is None:
            return False
        return inventory.stock_quantity <= inventory.low_stock_threshold


class ProductImage(TenantModelMixin):
    """An image belonging to a product."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image_url = models.URLField()
    alt_text = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """ProductImage model metadata."""

        db_table = "product_images"
        ordering = ["sort_order", "created_at"]

    def __str__(self) -> str:
        """Return image label."""
        return f"Image: {self.product.name} ({self.sort_order})"


class Inventory(TenantModelMixin):
    """Per-product stock tracking."""

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    track_inventory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Inventory model metadata."""

        db_table = "inventories"

    def __str__(self) -> str:
        """Return inventory label."""
        return f"Inventory: {self.product.name} ({self.stock_quantity})"


class Cart(TenantModelMixin):
    """A tenant-scoped shopping cart owned by a user."""

    class Status(models.TextChoices):
        """Lifecycle status of a cart."""

        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="marketplace_carts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Cart model metadata."""

        db_table = "carts"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return cart label."""
        return f"Cart: {self.user.email} ({self.status})"

    @property
    def total(self) -> float:
        """Return the cart subtotal rounded to two decimals."""
        return round(
            sum(float(item.total_price) for item in self.items.all()),
            2,
        )


class CartItem(TenantModelMixin):
    """A line item within a cart."""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """CartItem model metadata."""

        db_table = "cart_items"
        ordering = ["created_at"]

    def __str__(self) -> str:
        """Return cart item label."""
        return f"{self.quantity} x {self.product.name}"

    @property
    def total_price(self) -> float:
        """Return the line total rounded to two decimals."""
        return round(float(self.unit_price) * self.quantity, 2)

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist and snapshot the product price when not already set."""
        if not self.unit_price:
            self.unit_price = self.product.price
        super().save(*args, **kwargs)


class Order(TenantModelMixin):
    """A tenant-scoped order placed from a user's cart."""

    class Status(models.TextChoices):
        """Lifecycle status of an order."""

        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        """Payment lifecycle status of an order."""

        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    uuid = models.UUIDField(
        default=uuid_lib.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="marketplace_orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_address = models.TextField(blank=True)
    billing_address = models.TextField(blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Order model metadata."""

        db_table = "orders"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return order label."""
        return f"Order: {self.uuid} ({self.status})"


class OrderItem(TenantModelMixin):
    """A line item within an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """OrderItem model metadata."""

        db_table = "order_items"
        ordering = ["created_at"]

    def __str__(self) -> str:
        """Return order item label."""
        return f"{self.quantity} x {self.product.name}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist and auto-calculate the line total from unit price and quantity."""
        if not self.total_price:
            self.total_price = float(self.unit_price) * self.quantity
        super().save(*args, **kwargs)
