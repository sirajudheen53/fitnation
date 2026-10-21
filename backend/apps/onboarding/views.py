"""Onboarding API views — thin wrappers over the orchestration service."""

from typing import Any, ClassVar

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.serializers import OnboardingVerifyPaymentSerializer
from apps.onboarding.services import (
    OnboardingError,
    complete_razorpay_onboarding,
    create_member_onboarding,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication

# Any-of the permissions the wizard touches (onboarding-design §3): a
# front-desk role holding all three passes; a role missing one (e.g. cannot
# record payments) is a 403 before any write. RolePermission treats
# set-valued ``required_permission`` as any-of.
ONBOARDING_PERMISSIONS = {
    "customers.create_customer",
    "memberships.create_membership",
    "payments.record_payment",
}


class OnboardingMemberView(APIView):
    """`POST /api/v1/onboarding/member/` — the whole wizard in one call."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = ONBOARDING_PERMISSIONS

    def post(self, request: Request) -> Response:
        """Create customer + membership + payment (+ biometrics) and fire invites.

        Idempotent: an ``Idempotency-Key`` header replays the stored result;
        without a key, re-submitting the same member onto the same plan on
        the same day returns the first result instead of double-selling.

        Returns:
            ``201`` with the composite result, ``400`` on contract errors,
            ``403`` when the caller lacks any of the three permissions,
            ``502`` when the Razorpay order cannot be created.
        """
        idempotency_key = str(request.headers.get("Idempotency-Key", "")).strip()[:64]
        try:
            result = create_member_onboarding(
                tenant=request.tenant,
                user=request.user,
                payload=request.data,
                request=request,
                idempotency_key=idempotency_key,
            )
        except OnboardingError as exc:
            return Response(exc.detail, status=exc.status_code)
        return Response(result, status=201)


class OnboardingVerifyPaymentView(APIView):
    """`POST /api/v1/onboarding/member/{uuid}/verify-payment/` — Razorpay phase 2."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = ONBOARDING_PERMISSIONS

    def post(self, request: Request, uuid: str) -> Response:
        """Verify the checkout signature, then create membership + extras.

        Returns:
            ``201`` with the same composite shape as the cash path, ``400``
            on a bad signature (payment failed, session re-orderable),
            ``404``/``409`` for unknown or non-pending sessions.
        """
        serializer = OnboardingVerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result: dict[str, Any] = complete_razorpay_onboarding(
                tenant=request.tenant,
                user=request.user,
                session_uuid=uuid,
                razorpay_order_id=serializer.validated_data["razorpay_order_id"],
                razorpay_payment_id=serializer.validated_data["razorpay_payment_id"],
                razorpay_signature=serializer.validated_data["razorpay_signature"],
            )
        except OnboardingError as exc:
            return Response(exc.detail, status=exc.status_code)
        return Response(result, status=201)
