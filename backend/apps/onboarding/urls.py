"""Onboarding app URL configuration (mounted at api/v1/onboarding/)."""

from django.urls import path

from apps.onboarding.views import OnboardingMemberView, OnboardingVerifyPaymentView

urlpatterns = [
    path("member/", OnboardingMemberView.as_view(), name="onboarding-member"),
    path(
        "member/<uuid:uuid>/verify-payment/",
        OnboardingVerifyPaymentView.as_view(),
        name="onboarding-verify-payment",
    ),
]
