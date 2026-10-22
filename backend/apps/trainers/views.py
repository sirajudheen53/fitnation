"""Trainer management API views (FBOS-007, issue #52)."""

from typing import ClassVar

from django.db import transaction
from django.db.models import Avg, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.trainers.models import TrainerAssignment, TrainerPerformance, TrainerSession
from apps.trainers.serializers import (
    TrainerAssignmentSerializer,
    TrainerPerformanceSerializer,
    TrainerScheduleSerializer,
    TrainerSerializer,
    TrainerSessionSerializer,
)
from apps.trainers.services import assert_no_slot_conflict, book_session, transition_session
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import Trainer, TrainerSchedule


class TrainerViewSet(viewsets.ModelViewSet):
    """Tenant-scoped trainer management.

    ``users.Trainer`` carries its tenant via the linked ``User`` record, so the
    queryset is scoped through ``user__tenant`` rather than a ``for_tenant`` manager.
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_trainer"
    serializer_class = TrainerSerializer
    http_method_names: ClassVar[list[str]] = ["get", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        """Return trainers belonging to the request's tenant."""
        return Trainer.objects.select_related("user").filter(user__tenant=self.request.tenant).order_by("-created_at")

    @action(detail=True, methods=["get"], url_path="performance")
    def performance(self, request: Request, pk: int) -> Response:
        """Return aggregated monthly performance metrics for a trainer."""
        trainer = self.get_object()
        records = TrainerPerformance.objects.filter(
            tenant=request.tenant,
            trainer=trainer,
        )
        aggregate = records.aggregate(
            total_revenue=Sum("revenue"),
            total_sessions=Sum("sessions_completed"),
            avg_rating=Avg("rating_avg"),
            avg_customers=Avg("customer_count"),
        )
        latest = records.order_by("-month").first()
        return Response(
            {
                "trainer_id": trainer.id,
                "total_revenue": aggregate["total_revenue"] or 0,
                "total_sessions_completed": aggregate["total_sessions"] or 0,
                "average_rating": aggregate["avg_rating"],
                "average_customer_count": aggregate["avg_customers"] or 0,
                "latest_month": latest.month if latest else None,
                "monthly_records": TrainerPerformanceSerializer(records, many=True).data,
            }
        )


class TrainerAssignmentViewSet(viewsets.ModelViewSet):
    """Tenant-scoped branch-level trainer↔customer assignments."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.edit_trainer"
    serializer_class = TrainerAssignmentSerializer
    http_method_names: ClassVar[list[str]] = ["get", "post", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        """Return assignments belonging to the request's tenant."""
        return TrainerAssignment.objects.for_tenant(self.request.tenant).select_related(
            "trainer__user", "customer", "branch"
        )

    def perform_create(self, serializer):
        """Create an assignment scoped to the request's tenant."""
        serializer.save(tenant=self.request.tenant)

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request: Request, pk: int) -> Response:
        """Reactivate an assignment or mark it active again."""
        assignment = self.get_object()
        assignment.is_active = True
        assignment.unassigned_at = None
        assignment.save(update_fields=["is_active", "unassigned_at"])
        return Response(TrainerAssignmentSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="unassign")
    def unassign(self, request: Request, pk: int) -> Response:
        """Deactivate an assignment and record the unassign timestamp."""
        assignment = self.get_object()
        assignment.is_active = False
        assignment.unassigned_at = timezone.now()
        assignment.save(update_fields=["is_active", "unassigned_at"])
        return Response(TrainerAssignmentSerializer(assignment).data)


class TrainerPerformanceViewSet(viewsets.ModelViewSet):
    """Tenant-scoped monthly trainer performance snapshots."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_trainer"
    serializer_class = TrainerPerformanceSerializer
    filterset_fields: ClassVar[list[str]] = ["trainer", "month"]
    pagination_class = None

    def get_queryset(self):
        """Return performance records belonging to the request's tenant."""
        return TrainerPerformance.objects.for_tenant(self.request.tenant).select_related("trainer__user")

    def perform_create(self, serializer):
        """Create a performance record, scoped to the request's tenant."""
        serializer.save(tenant=self.request.tenant)


class TrainerScheduleViewSet(viewsets.ModelViewSet):
    """Tenant-scoped weekly availability schedules for trainers."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_trainer"
    serializer_class = TrainerScheduleSerializer
    filterset_fields: ClassVar[list[str]] = ["trainer", "day_of_week"]
    pagination_class = None

    def get_queryset(self):
        """Return schedules belonging to the request's tenant."""
        return TrainerSchedule.objects.for_tenant(self.request.tenant).select_related("trainer__user")

    def perform_create(self, serializer):
        """Create a schedule entry, scoped to the request's tenant."""
        serializer.save(tenant=self.request.tenant)


class TrainerSessionViewSet(viewsets.ModelViewSet):
    """Tenant-scoped PT sessions with the booking + redemption lifecycle (issue #52).

    Booking (POST) enforces the customer's PT pack — 409 with a machine-readable
    ``reason`` when there is no active PT membership, it expired, the pack is
    exhausted, or the trainer's slot overlaps. ``completed`` / ``no_show``
    transitions redeem one pack credit and feed the trainer's monthly
    performance; ``cancelled`` never redeems (and restores a redeemed credit).
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_session"
    method_permissions: ClassVar[dict] = {
        "POST": "trainers.edit_session",
        "PUT": "trainers.edit_session",
        "PATCH": "trainers.edit_session",
    }
    serializer_class = TrainerSessionSerializer
    filterset_fields: ClassVar[list[str]] = ["trainer", "customer", "branch", "status"]
    pagination_class = None
    ordering: ClassVar[list[str]] = ["-scheduled_at"]

    def get_queryset(self):
        """Return sessions belonging to the request's tenant."""
        return TrainerSession.objects.for_tenant(self.request.tenant).select_related(
            "trainer__user",
            "customer",
            "branch",
        )

    def perform_create(self, serializer):
        """Book through the service so entitlement + overlap gates apply."""
        data = serializer.validated_data
        serializer.instance = book_session(
            tenant=self.request.tenant,
            trainer=data["trainer"],
            customer=data["customer"],
            branch=data.get("branch"),
            scheduled_at=data["scheduled_at"],
            duration_minutes=data.get("duration_minutes") or 60,
            notes=data.get("notes") or "",
        )

    def perform_update(self, serializer):
        """Re-run the overlap guard when the slot moves; plain save for notes.

        Atomic so the trainer-row lock from the overlap check is held until
        the save commits (no check-then-write race).
        """
        data = serializer.validated_data
        with transaction.atomic():
            if "scheduled_at" in data or "duration_minutes" in data:
                instance = serializer.instance
                assert_no_slot_conflict(
                    tenant=instance.tenant,
                    trainer=data.get("trainer", instance.trainer),
                    scheduled_at=data.get("scheduled_at", instance.scheduled_at),
                    duration_minutes=data.get("duration_minutes", instance.duration_minutes),
                    exclude_pk=instance.pk,
                )
            serializer.save()

    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: int) -> Response:
        """Mark the session completed — redeems one pack credit."""
        session = self.get_object()
        transition_session(session, TrainerSession.Status.COMPLETED)
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=["post"], url_path="no-show")
    def no_show(self, request: Request, pk: int) -> Response:
        """Mark the session as a no-show — redeems one pack credit."""
        session = self.get_object()
        transition_session(session, TrainerSession.Status.NO_SHOW)
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: int) -> Response:
        """Cancel the session — no redemption; restores a redeemed credit."""
        session = self.get_object()
        transition_session(session, TrainerSession.Status.CANCELLED)
        return Response(self.get_serializer(session).data)
