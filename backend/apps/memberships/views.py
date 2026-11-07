"""Membership management API views."""

from datetime import timedelta
from typing import ClassVar

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
    MembershipUpgradeSerializer,
)
from apps.memberships.services import assert_no_membership_overlap, prorated_upgrade_suggestion
from apps.notifications.services.invite_service import REASON_DAILY_LIMIT, invite_result_payload, send_app_invite
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
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

        The list serializer reads customer and plan fields — join them so a
        page costs one query instead of three per row (#82).
        """
        queryset = Membership.objects.for_tenant(self.request.tenant).select_related("customer", "plan")
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

        The extension may not reach into another ACTIVE membership's period
        (issue #104) — the same row is exempt, cancelled/expired rows don't
        count; a violating extension is rejected with a 400 naming the
        conflicting membership.
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

        # Issue #104: the extension must not reach into another ACTIVE
        # membership's period. The row itself is excluded — extending the
        # same membership is never a self-overlap — but an extension that
        # would overlap a different active membership is blocked (no
        # auto-supersede), before any field is mutated.
        assert_no_membership_overlap(
            tenant=request.tenant,
            customer=membership.customer,
            start_date=membership.start_date,
            end_date=new_end,
            exclude_pk=membership.pk,
        )

        membership.plan = plan
        membership.end_date = new_end
        membership.status = Membership.Status.ACTIVE
        membership.refresh_status()
        membership.save()
        self._propagate_access_change(membership)
        return Response(MembershipSerializer(membership).data)

    @action(detail=True, methods=["get", "post"])
    def upgrade(self, request: Request, pk: int) -> Response:
        """Upgrade a membership onto a higher-priced plan (#105).

        Owner decision (2026-11-07): the upgrade amount is SUGGESTED — the
        prorated price difference over the remaining paid days is pre-filled
        for the desk — and the entered amount is what gets recorded as the
        payment (staff judgment always wins). The end date stays UNCHANGED:
        the upgrade swaps the plan within the already-paid window.

        GET returns the display-only suggestion for every eligible
        (higher-priced, active) tenant plan plus the remaining days, so the
        ERP dialog can pre-fill the amount without recomputing business
        rules client-side.

        POST swaps the plan, keeps ``end_date`` and records a COMPLETED
        payment for the human-entered amount. Downgrades — a plan priced at
        or below the current one — are rejected as a guardrail. After the
        swap the access change propagates (door allow-lists + ADMS gate);
        the app entitlement derives per-request from the new plan's
        ``includes_app_access`` flag, so it stays consistent without a
        separate step.
        """
        membership = self.get_object()

        if request.method == "GET":
            remaining_days = max(0, (membership.end_date - timezone.localdate()).days + 1)
            eligible_plans = []
            for plan in (
                MembershipPlan.objects.for_tenant(request.tenant).filter(is_active=True).order_by("price", "id")
            ):
                if plan.pk == membership.plan_id or plan.price <= membership.plan.price:
                    continue
                suggestion = prorated_upgrade_suggestion(
                    current_plan=membership.plan,
                    new_plan=plan,
                    end_date=membership.end_date,
                )
                eligible_plans.append(
                    {
                        "id": plan.id,
                        "name": plan.name,
                        "price": str(plan.price),
                        "duration_days": plan.duration_days,
                        "suggested_amount": str(suggestion["suggested_amount"]),
                    }
                )
            return Response(
                {
                    "membership_id": membership.id,
                    "end_date": membership.end_date.isoformat(),
                    "remaining_days": remaining_days,
                    "current_plan": {
                        "id": membership.plan.id,
                        "name": membership.plan.name,
                        "price": str(membership.plan.price),
                        "duration_days": membership.plan.duration_days,
                    },
                    "eligible_plans": eligible_plans,
                },
            )

        self.required_permission = "memberships.edit_membership"
        if membership.status != Membership.Status.ACTIVE:
            return Response(
                {"detail": "Only an active membership can be upgraded — renew it instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = MembershipUpgradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        new_plan = (
            MembershipPlan.objects.for_tenant(request.tenant)
            .filter(
                id=validated["plan_id"],
            )
            .first()
        )
        if new_plan is None:
            return Response(
                {"plan_id": ["Invalid plan for this gym."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_plan.price <= membership.plan.price:
            return Response(
                {
                    "plan_id": [
                        f"Downgrade not allowed — {new_plan.name} costs less than or the same "
                        f"as the current plan ({membership.plan.name}). Pick a higher-priced plan."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        suggestion = prorated_upgrade_suggestion(
            current_plan=membership.plan,
            new_plan=new_plan,
            end_date=membership.end_date,
        )
        amount = validated["amount"]
        with transaction.atomic():
            membership.plan = new_plan
            membership.save()
            payment = Payment.objects.create(
                tenant=request.tenant,
                customer=membership.customer,
                membership=membership,
                amount=amount,
                payment_method=validated["payment_method"],
                status=Payment.Status.COMPLETED,
                paid_at=timezone.now(),
                notes=validated["notes"],
            )

        # After commit: the syncs below call out to devices and must not run
        # inside a transaction holding the membership row locked.
        self._propagate_access_change(membership)
        return Response(
            {
                "membership": MembershipSerializer(membership).data,
                "payment": PaymentSerializer(payment).data,
                "suggested_amount": str(suggestion["suggested_amount"]),
                "amount_charged": str(amount),
            },
        )


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
