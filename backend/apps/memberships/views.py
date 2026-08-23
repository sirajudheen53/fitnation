"""Membership management API views."""

from datetime import timedelta

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.memberships.serializers import (
    CouponSerializer,
    MembershipPlanSerializer,
    MembershipSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class MembershipPlanViewSet(ModelViewSet):
    """Tenant-scoped membership plan CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
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

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "memberships.view_membership"
    serializer_class = MembershipSerializer

    def get_queryset(self) -> Membership:
        """Return memberships scoped to the request tenant."""
        return Membership.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new membership, validating dates and status."""
        self.required_permission = "memberships.create_membership"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save(tenant=request.tenant)
        membership.refresh_status()
        membership.save(update_fields=["status"])
        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

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
    def renewal(self, request: Request, pk: int) -> Response:
        """Renew a membership by extending end_date and refreshing status."""
        self.required_permission = "memberships.edit_membership"
        membership = self.get_object()

        days = request.data.get("days")
        if days is None:
            days = membership.plan.duration_days or 30
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

        membership.end_date = new_end
        membership.status = Membership.Status.ACTIVE
        membership.refresh_status()
        membership.save()
        return Response(MembershipSerializer(membership).data)


class CouponViewSet(ModelViewSet):
    """Tenant-scoped coupon CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
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
