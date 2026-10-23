"""Membership management API views."""

from datetime import timedelta
from typing import ClassVar

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.access.propagation import propagate_customer_biometric_state
from apps.access.services import sync_customer_devices
from apps.customers.models import Customer
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.memberships.serializers import (
    AppInviteSerializer,
    CouponSerializer,
    MembershipPlanSerializer,
    MembershipSerializer,
)
from apps.notifications.services.invite_service import REASON_DAILY_LIMIT, invite_result_payload, send_app_invite
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.auth import AuthToken
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import User


class MembershipPlanViewSet(ModelViewSet):
    """Tenant-scoped membership plan CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "memberships.view_membership"
    serializer_class = MembershipPlanSerializer

    def get_queryset(self) -> MembershipPlan:
        """Return plans scoped to the request tenant."""
        return MembershipPlan.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new membership plan."""
        self.required_permission = "memberships.create_membership"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save(tenant=request.tenant)
        return Response(
            MembershipPlanSerializer(plan).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a membership plan."""
        self.required_permission = "memberships.edit_membership"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a membership plan."""
        self.required_permission = "memberships.edit_membership"
        return super().partial_update(request, *args, **kwargs)


class MembershipViewSet(ModelViewSet):
    """Tenant-scoped membership CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "memberships.view_membership"
    serializer_class = MembershipSerializer

    def get_queryset(self) -> Membership:
        """Return memberships scoped to the request tenant.

        Customer-role users see only their own memberships.
        """
        queryset = Membership.objects.for_tenant(self.request.tenant)
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(customer__user=self.request.user)
        return queryset

    def _propagate_access_change(self, membership: Membership) -> None:
        """Push updated allow-lists + user metadata to the customer's devices.

        Two halves, both synchronous by design (this project has no
        Celery; access changes must reach door hardware within ~5s):
        the allow-list/door sync (issue #24) and the ADMS user-metadata
        gate — queue DATA UPDATE/DELETE USERINFO per enrolled device so
        the device's user table mirrors membership state, cool-off
        included (phase 2).
        """
        sync_customer_devices(membership.customer)
        propagate_customer_biometric_state(customer=membership.customer)

    def create(self, request: Request) -> Response:
        """Create a new membership, validating dates and status."""
        self.required_permission = "memberships.create_membership"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save(tenant=request.tenant)
        membership.refresh_status()
        membership.save(update_fields=["status"])
        self._propagate_access_change(membership)
        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer: MembershipSerializer) -> None:
        """Save membership edits, then propagate access changes."""
        membership = serializer.save()
        self._propagate_access_change(membership)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a membership."""
        self.required_permission = "memberships.edit_membership"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a membership."""
        self.required_permission = "memberships.edit_membership"
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: int) -> Response:
        """Cancel a membership by setting its status to cancelled.

        When the rollout flag is on and the customer holds no other
        non-cancelled membership, the customer's auth tokens are revoked too
        (FBOS-011 §9.4): cancellation is a business act — access dies with the
        session, re-login lands them on the ``none`` gate. Legacy tenants
        (flag off) keep today's behaviour.
        """
        self.required_permission = "memberships.edit_membership"
        membership = self.get_object()
        if membership.status != "cancelled":
            membership.status = "cancelled"
            membership.save(update_fields=["status", "updated_at"])
        self._propagate_access_change(membership)
        if (request.tenant.features or {}).get("app_access"):
            has_live_membership = (
                Membership.objects.for_tenant(request.tenant)
                .filter(customer=membership.customer)
                .exclude(status=Membership.Status.CANCELLED)
                .exclude(pk=membership.pk)
                .exists()
            )
            if not has_live_membership and membership.customer.user_id:
                AuthToken.objects.filter(user=membership.customer.user, is_active=True).update(is_active=False)
        return Response(self.get_serializer(membership).data)

    @action(detail=True, methods=["post"])
    def renewal(self, request: Request, pk: int) -> Response:
        """Renew a membership by extending end_date and refreshing status.

        An optional ``plan_id`` (must belong to this tenant) moves the
        membership onto that plan before the extension (issue #68); the
        default ``days`` then comes from the NEW plan's duration. Without
        ``plan_id`` the renewal extends the current plan as before.
        """
        self.required_permission = "memberships.edit_membership"
        membership = self.get_object()

        plan = membership.plan
        plan_id = request.data.get("plan_id")
        if plan_id is not None:
            try:
                plan_id = int(plan_id)
            except (TypeError, ValueError):
                return Response(
                    {"plan_id": "Must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            plan = MembershipPlan.objects.for_tenant(request.tenant).filter(id=plan_id).first()
            if plan is None:
                return Response(
                    {"plan_id": "Invalid plan for this gym."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        days = request.data.get("days")
        if days is None:
            days = plan.duration_days or 30
        try:
            days = int(days)
        except (TypeError, ValueError):
            return Response(
                {"days": "Must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if days <= 0:
            return Response(
                {"days": "Must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_end = membership.end_date + timedelta(days=days)
        if new_end <= membership.end_date:
            return Response(
                {"detail": "Renewal must extend the membership."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.plan = plan
        membership.end_date = new_end
        membership.status = Membership.Status.ACTIVE
        membership.refresh_status()
        membership.save()
        self._propagate_access_change(membership)
        return Response(MembershipSerializer(membership).data)


class AppInviteView(APIView):
    """Send / resend the mobile-app invite to a member (FBOS-011 §5.1b).

    For members onboarded before invites existed or whose invite failed.
    Idempotent within ``APP_INVITE_RESEND_WINDOW_HOURS`` — a repeat call
    returns ``already_sent`` instead of double-messaging; ``resend: true``
    forces a new send (still capped by the tenant daily limit).
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "customers.edit_customer"

    def post(self, request: Request) -> Response:
        """Deliver the invite and report the outcome.

        Returns:
            ``201`` with the ``app_invite`` block for a fresh send, ``200``
            for ``already_sent`` / skipped / failed outcomes, ``429`` when
            the tenant's daily invite cap is hit, ``404`` for a customer
            outside the tenant.
        """
        serializer = AppInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = get_object_or_404(
            Customer.objects.for_tenant(request.tenant),
            id=serializer.validated_data["customer_id"],
        )

        result = send_app_invite(
            request.tenant,
            customer,
            invited_by=request.user,
            force=serializer.validated_data.get("resend", False),
        )
        if result.reason == REASON_DAILY_LIMIT:
            return Response(
                {"detail": "Daily app-invite limit reached for this gym. Try again tomorrow."},
                status=429,
            )
        payload = invite_result_payload(result)
        return Response(payload, status=201 if result.status == "sent" else 200)


class CouponViewSet(ModelViewSet):
    """Tenant-scoped coupon CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "memberships.view_membership"
    serializer_class = CouponSerializer

    def get_queryset(self) -> Coupon:
        """Return coupons scoped to the request tenant."""
        return Coupon.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new coupon."""
        self.required_permission = "memberships.create_membership"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.save(tenant=request.tenant)
        return Response(
            CouponSerializer(coupon).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a coupon."""
        self.required_permission = "memberships.edit_membership"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a coupon."""
        self.required_permission = "memberships.edit_membership"
        return super().partial_update(request, *args, **kwargs)
