"""Product marketplace serializers."""

from rest_framework import serializers

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


class ProductCategorySerializer(serializers.ModelSerializer):
    """Serialize product category details."""

    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        """Serializer metadata."""

        model = ProductCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "product_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "product_count", "created_at", "updated_at"]


class ProductImageSerializer(serializers.ModelSerializer):
    """Serialize product image details."""

    class Meta:
        """Serializer metadata."""

        model = ProductImage
        fields = ["id", "product", "image_url", "alt_text", "sort_order", "created_at"]
        read_only_fields = ["id", "created_at"]


class InventorySerializer(serializers.ModelSerializer):
    """Serialize inventory details."""

    class Meta:
        """Serializer metadata."""

        model = Inventory
        fields = [
            "id",
            "product",
            "stock_quantity",
            "low_stock_threshold",
            "track_inventory",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "product", "created_at", "updated_at"]


class ProductListSerializer(serializers.ModelSerializer):
    """Minimal product representation for list endpoints."""

    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Product
        fields = [
            "id",
            "uuid",
            "name",
            "slug",
            "category",
            "category_name",
            "price",
            "compare_price",
            "brand",
            "status",
            "is_digital",
            "is_low_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "category_name", "is_low_stock", "created_at", "updated_at"]


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full product representation for detail endpoints."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    inventory = InventorySerializer(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Product
        fields = [
            "id",
            "uuid",
            "category",
            "category_name",
            "name",
            "slug",
            "description",
            "price",
            "compare_price",
            "sku",
            "barcode",
            "brand",
            "status",
            "is_digital",
            "is_low_stock",
            "images",
            "inventory",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "category_name", "is_low_stock", "created_at", "updated_at"]


class ProductWriteSerializer(serializers.ModelSerializer):
    """Serializer for product create/update operations."""

    images = ProductImageSerializer(many=True, required=False)
    inventory = InventorySerializer(required=False)

    class Meta:
        """Serializer metadata."""

        model = Product
        fields = [
            "category",
            "name",
            "slug",
            "description",
            "price",
            "compare_price",
            "sku",
            "barcode",
            "brand",
            "status",
            "is_digital",
            "images",
            "inventory",
        ]

    def create(self, validated_data: dict) -> Product:
        """Create a product and its optional nested images/inventory."""
        images_data = validated_data.pop("images", [])
        inventory_data = validated_data.pop("inventory", None)
        product = Product.objects.create(**validated_data)

        for image_data in images_data:
            ProductImage.objects.create(product=product, **image_data)

        if inventory_data is not None:
            Inventory.objects.create(product=product, tenant_id=product.tenant_id, **inventory_data)
        else:
            Inventory.objects.create(product=product, tenant_id=product.tenant_id)

        return product

    def update(self, instance: Product, validated_data: dict) -> Product:
        """Update a product and its nested images/inventory."""
        images_data = validated_data.pop("images", [])
        inventory_data = validated_data.pop("inventory", None)

        instance = super().update(instance, validated_data)

        if images_data is not None:
            instance.images.all().delete()
            for image_data in images_data:
                ProductImage.objects.create(product=instance, **image_data)

        if inventory_data is not None:
            inventory, _ = Inventory.objects.get_or_create(product=instance)
            for attr, value in inventory_data.items():
                setattr(inventory, attr, value)
            inventory.save()

        return instance


class CartItemSerializer(serializers.ModelSerializer):
    """Serialize a cart line item."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = CartItem
        fields = [
            "id",
            "cart",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["id", "cart", "product_name", "total_price", "created_at"]


class CartSerializer(serializers.ModelSerializer):
    """Serialize a cart with its line items."""

    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Cart
        fields = [
            "id",
            "user",
            "status",
            "items",
            "total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "items", "total", "created_at", "updated_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    """Serialize an order line item."""

    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = OrderItem
        fields = [
            "id",
            "order",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["id", "order", "product_name", "created_at"]


class OrderListSerializer(serializers.ModelSerializer):
    """Minimal order representation for list endpoints."""

    class Meta:
        """Serializer metadata."""

        model = Order
        fields = [
            "id",
            "uuid",
            "status",
            "total_amount",
            "payment_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "created_at", "updated_at"]


class OrderDetailSerializer(serializers.ModelSerializer):
    """Full order representation with line items."""

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Order
        fields = [
            "id",
            "uuid",
            "user",
            "status",
            "total_amount",
            "shipping_address",
            "billing_address",
            "payment_status",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "uuid",
            "user",
            "total_amount",
            "items",
            "created_at",
            "updated_at",
        ]


class OrderWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating orders from a cart."""

    class Meta:
        """Serializer metadata."""

        model = Order
        fields = [
            "status",
            "shipping_address",
            "billing_address",
            "payment_status",
        ]


class OrderItemWriteSerializer(serializers.ModelSerializer):
    """Serializer for adding order line items."""

    class Meta:
        """Serializer metadata."""

        model = OrderItem
        fields = ["product", "quantity"]
