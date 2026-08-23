"""Users app URL configuration."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.users.views import (
    LoginView,
    LogoutView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    TrainerViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"trainers", TrainerViewSet, basename="trainer")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("auth/otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    *router.urls,
]
