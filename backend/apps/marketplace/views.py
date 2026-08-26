"""Product marketplace API views."""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.marketplace.models import (
    CartItem,
    Order,
    OrderItem,
    Product,
    ProductCategory,
)
from apps.marketplace.serializers import (
    CartSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderListSerializer,
    OrderWriteSerializer,
    ProductCategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductWriteSerializer,
)
from apps.marketplace import services
from apps.marketplace.selectors import get_or_create_active_cart
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class ProductCategoryViewSet(ModelViewSet):
    """Tenant-scoped CRUD for product categories."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "marketplace.view_product"
    method_permissions = {
        "GET": "marketplace.view_product",
        "POST": "marketplace.edit_product",
        "PUT": "marketplace.edit_product",
        "PATCH": "marketplace.edit_product",
        "DELETE": "marketplace.delete_product",
    }
    serializer_class = ProductCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "slug"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self) -> ProductCategory:
        """Return categories scoped to the tenant with product counts."""
        return (
            ProductCategory.objects.for_tenant(self.request.tenant)
            .annotate(product_count=Count("products"))
            .all()
        )

    def perform_create(self, serializer: ProductCategorySerializer) -> None:
        """Persist the new category scoped to the request tenant."""
        serializer.save(tenant=self.request.tenant)
        instance = serializer.instance
        instance.product_count = instance.products.count()


class ProductViewSet(ModelViewSet):
    """Tenant-scoped CRUD for products with search and filtering."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "marketplace.view_product"
    method_permissions = {
        "GET": "marketplace.view_product",
        "POST": "marketplace.edit_product",
        "PUT": "marketplace.edit_product",
        "PATCH": "marketplace.edit_product",
        "DELETE": "marketplace.delete_product",
    }
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "brand", "sku"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self) -> Product:
        """Return products scoped to the tenant with optional filters."""
        queryset = (
            Product.objects.for_tenant(self.request.tenant)
            .select_related("category")
            .prefetch_related("images", "inventory")
        )
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def get_serializer_class(self):
        """Return a product serializer matching the request action."""
        if self.action == "list":
            return ProductListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return ProductWriteSerializer
        return ProductDetailSerializer

    def perform_create(self, serializer: ProductWriteSerializer) -> None:
        """Persist the new product scoped to the request tenant."""
        serializer.save(tenant=self.request.tenant)


class CartView(APIView):
    """Retrieve, add-to, or clear the current user's active cart."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "marketplace.view_cart"

    def get(self, request: Request) -> Response:
        """Return the current user's active cart."""
        self.required_permission = "marketplace.view_cart"
        cart = get_or_create_active_cart(tenant=request.tenant, user=request.user)
        return Response(CartSerializer(cart).data)

    def post(self, request: Request) -> Response:
        """Add an item to the current user's active cart."""
        self.required_permission = "marketplace.edit_cart"
        product_id = request.data.get("product")
        quantity_raw = request.data.get("quantity", 1)
        try:
            quantity = int(quantity_raw) if quantity_raw is not None else 1
        except (TypeError, ValueError):
            return Response(
                {"quantity": "Quantity must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if quantity < 1:
            return Response(
                {"quantity": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = get_object_or_404(
            Product.objects.for_tenant(request.tenant),
            id=product_id,
        )
        services.add_item_to_cart(
            tenant=request.tenant,
            user=request.user,
            product=product,
            quantity=quantity,
        )
        cart = get_or_create_active_cart(tenant=request.tenant, user=request.user)
        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request) -> Response:
        """Clear all items from the current user's active cart."""
        self.required_permission = "marketplace.edit_cart"
        services.clear_cart(tenant=request.tenant, user=request.user)
        cart = get_or_create_active_cart(tenant=request.tenant, user=request.user)
        return Response(CartSerializer(cart).data)


class CartItemView(APIView):
    """Update quantity or remove a specific cart line item."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "marketplace.view_cart"

    def get_object(self, request: Request, item_id: int) -> CartItem:
        """Return a cart item scoped to the request tenant and user's active cart."""
        cart = get_or_create_active_cart(tenant=request.tenant, user=request.user)
        return get_object_or_404(CartItem.objects.for_tenant(request.tenant), id=item_id, cart=cart)

    def patch(self, request: Request, item_id: int) -> Response:
        """Update the quantity of a cart line item."""
        self.required_permission = "marketplace.edit_cart"
        item = self.get_object(request, item_id)
        quantity_raw = request.data.get("quantity", item.quantity)
        try:
            quantity = int(quantity_raw) if quantity_raw is not None else item.quantity
        except (TypeError, ValueError):
            quantity = item.quantity
        if quantity < 1:
            return Response(
                {"quantity": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        cart = get_or_create_active_cart(tenant=request.tenant, user=request.user)
        return Response(CartSerializer(cart).data)

    def delete(self, request: Request, item_id: int) -> Response:
        """Remove a cart line item."""
        self.required_permission = "marketplace.edit_cart"
        item = self.get_object(request, item_id)
        item.delete()
        cart = get_or_create_active_cart(tenant=request.tenant, user=request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class OrderViewSet(ModelViewSet):
    """Tenant-scoped CRUD for orders."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "marketplace.view_order"
    method_permissions = {
        "GET": "marketplace.view_order",
        "POST": "marketplace.create_order",
        "PUT": "marketplace.edit_order",
        "PATCH": "marketplace.edit_order",
        "DELETE": "marketplace.delete_order",
    }
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["uuid", "status", "payment_status"]
    ordering_fields = ["created_at", "total_amount"]
    ordering = ["-created_at"]

    def get_queryset(self) -> Order:
        """Return orders scoped to the tenant, optionally filtered by user."""
        queryset = Order.objects.for_tenant(self.request.tenant).prefetch_related("items")
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

    def get_serializer_class(self):
        """Return a serializer matching the request action."""
        if self.action == "list":
            return OrderListSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        if self.action in {"create", "update", "partial_update"}:
            return OrderWriteSerializer
        if self.action == "items":
            return OrderItemSerializer
        return OrderListSerializer

    def create(self, request: Request) -> Response:
        """Place an order from the current user's cart."""
        self.required_permission = "marketplace.create_order"
        try:
            order = services.place_order(
                tenant=request.tenant,
                user=request.user,
                shipping_address=request.data.get("shipping_address", ""),
                billing_address=request.data.get("billing_address", ""),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request: Request, pk: int) -> Response:
        """List the line items of a specific order."""
        self.required_permission = "marketplace.view_order"
        order = get_object_or_404(
            Order.objects.for_tenant(request.tenant),
            id=pk,
        )
        order_items = OrderItem.objects.for_tenant(request.tenant).filter(order=order)
        return Response(OrderItemSerializer(order_items, many=True).data)
