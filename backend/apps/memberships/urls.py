"""Memberships app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.memberships.views import (
    CouponViewSet,
    MembershipPlanViewSet,
    MembershipViewSet,
)

router = DefaultRouter()
router.register(r"memberships", MembershipViewSet, basename="membership")
router.register(r"membership-plans", MembershipPlanViewSet, basename="membership-plan")
router.register(r"coupons", CouponViewSet, basename="coupon")

urlpatterns = [
    path("", include(router.urls)),
]
