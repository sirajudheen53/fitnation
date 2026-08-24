"""Marketplace admin configuration."""

from django.contrib import admin

from apps.marketplace.models import (
    Cart,
    CartItem,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    ProductImage,
)


class ProductImageInline(admin.TabularInline):
    """Inline editor for product images."""

    model = ProductImage
    extra = 1


class InventoryInline(admin.StackedInline):
    """Inline editor for product inventory."""

    model = Inventory
    can_delete = False


class CartItemInline(admin.TabularInline):
    """Inline editor for cart items."""

    model = CartItem
    extra = 0


class OrderItemInline(admin.TabularInline):
    """Inline editor for order items."""

    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "unit_price", "total_price"]


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    """Admin for product categories."""

    list_display = ["name", "slug", "tenant", "created_at"]
    list_filter = ["tenant"]
    search_fields = ["name", "slug"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for products."""

    list_display = [
        "name",
        "category",
        "price",
        "status",
        "brand",
        "is_digital",
        "tenant",
        "created_at",
    ]
    list_filter = ["status", "is_digital", "tenant", "category"]
    search_fields = ["name", "sku", "barcode", "brand"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, InventoryInline]
    readonly_fields = ["uuid"]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Admin for product images."""

    list_display = ["product", "image_url", "alt_text", "sort_order", "created_at"]
    search_fields = ["product__name", "alt_text"]


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    """Admin for inventory records."""

    list_display = [
        "product",
        "stock_quantity",
        "low_stock_threshold",
        "track_inventory",
        "tenant",
    ]
    list_filter = ["track_inventory", "tenant"]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Admin for carts."""

    list_display = ["id", "user", "status", "tenant", "created_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["user__email"]
    inlines = [CartItemInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin for orders."""

    list_display = [
        "id",
        "uuid",
        "user",
        "status",
        "payment_status",
        "total_amount",
        "tenant",
        "created_at",
    ]
    list_filter = ["status", "payment_status", "tenant"]
    search_fields = ["uuid", "user__email"]
    readonly_fields = ["uuid"]
    inlines = [OrderItemInline]
