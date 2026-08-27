"""Vendor onboarding API views."""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication
from apps.vendors.models import VendorRegistration
from apps.vendors.selectors import active_subscription_plans
from apps.vendors.serializers import (
    EmailVerificationSerializer,
    OnboardingSerializer,
    ResendVerificationSerializer,
    SelectPlanSerializer,
    SignupSerializer,
    SubscriptionPlanSerializer,
)
from apps.vendors.services import (
    complete_onboarding,
    create_vendor_registration,
    resend_verification_email,
    select_plan_and_provision,
    verify_registration_email,
)


class SignupView(APIView):
    """Create a vendor registration and trigger verification."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Handle vendor signup.

        Args:
            request: The incoming DRF request.

        Returns:
            Registration id, message, and next step.
        """
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        reg = create_vendor_registration(
            business_name=data["business_name"],
            contact_name=data["contact_name"],
            email=data["email"],
            phone=data.get("phone", ""),
            password=data["password"],
        )

        return Response(
            {
                "registration_id": reg.id,
                "message": f"Verification email sent to {reg.email}",
                "next_step": "verify_email",
            },
            status=status.HTTP_201_CREATED,
        )


class EmailVerifyView(APIView):
    """Verify a vendor email via token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Handle email verification.

        Args:
            request: The incoming DRF request.

        Returns:
            Success response with next step, or error if token is invalid.
        """
        serializer = EmailVerificationSerializer(
            data={"token": request.query_params.get("token", "")},
        )
        serializer.is_valid(raise_exception=True)
        token = str(serializer.validated_data["token"])

        try:
            reg = verify_registration_email(token)
        except VendorRegistration.DoesNotExist:
            return Response(
                {"error": "Invalid or expired verification token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Email verified successfully",
                "registration_id": reg.id,
                "next_step": "select_plan",
            }
        )


class ResendVerificationView(APIView):
    """Resend verification email for a pending registration."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Handle resend verification.

        Args:
            request: The incoming DRF request.

        Returns:
            Confirmation message.
        """
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            resend_verification_email(email)
        except VendorRegistration.DoesNotExist:
            return Response(
                {"error": "Registration not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"message": "Verification email re-sent"})


class SubscriptionPlanListView(APIView):
    """List active subscription plans."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Return active subscription plans.

        Args:
            request: The incoming DRF request.

        Returns:
            List of subscription plans.
        """
        plans = active_subscription_plans()
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response({"plans": serializer.data})


class SelectPlanView(APIView):
    """Select a plan and provision the tenant + owner user."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Handle plan selection and provisioning.

        Args:
            request: The incoming DRF request.

        Returns:
            Tenant, auth token, and next step.
        """
        serializer = SelectPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = select_plan_and_provision(data["registration_id"], data["plan_code"])
        except VendorRegistration.DoesNotExist:
            return Response(
                {"error": "Invalid registration or already provisioned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = result["tenant"]
        token = result["token"]
        return Response(
            {
                "message": "Workspace provisioned successfully",
                "tenant": {
                    "id": tenant.id,
                    "uuid": str(tenant.uuid),
                    "name": tenant.name,
                    "subscription_plan": tenant.subscription_plan,
                },
                "auth_token": token.key,
                "next_step": result["next_step"],
            },
            status=status.HTTP_201_CREATED,
        )


class OnboardingView(APIView):
    """Complete onboarding by creating the default branch."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]

    def put(self, request: Request) -> Response:
        """Handle onboarding completion.

        Args:
            request: The incoming DRF request.

        Returns:
            Onboarding completion confirmation.
        """
        serializer = OnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = complete_onboarding(
            user=request.user,
            business_type=data["business_type"],
            branches_count=data["branches_count"],
            primary_branch_name=data["primary_branch_name"],
            primary_branch_address=data["primary_branch_address"],
            primary_branch_phone=data.get("primary_branch_phone", ""),
        )

        return Response(
            {
                "message": result["message"],
                "redirect_to": result["redirect_to"],
                "branch_id": result["branch"].id,
            }
        )
