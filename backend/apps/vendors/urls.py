"""Vendors app URL configuration."""

from django.urls import path

from apps.vendors.views import (
    EmailVerifyView,
    OnboardingView,
    ResendVerificationView,
    SelectPlanView,
    SignupView,
    SubscriptionPlanListView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="vendor-signup"),
    path("verify-email/", EmailVerifyView.as_view(), name="vendor-verify-email"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="vendor-resend-verification",
    ),
    path("plans/", SubscriptionPlanListView.as_view(), name="vendor-plans"),
    path("select-plan/", SelectPlanView.as_view(), name="vendor-select-plan"),
    path("onboarding/", OnboardingView.as_view(), name="vendor-onboarding"),
]
