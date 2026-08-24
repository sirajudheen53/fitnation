"""Marketplace app URL configuration."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.marketplace.views import (
    CartItemView,
    CartView,
    OrderViewSet,
    ProductCategoryViewSet,
    ProductViewSet,
)

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"categories", ProductCategoryViewSet, basename="category")
router.register(r"orders", OrderViewSet, basename="order")

urlpatterns = [
    # Cart endpoints (custom APIView routes)
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/<int:item_id>/", CartItemView.as_view(), name="cart-item"),
    # Router-registered endpoints
    *router.urls,
]
