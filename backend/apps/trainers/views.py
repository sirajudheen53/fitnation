"""Trainer management API views (FBOS-007)."""

from django.db.models import Avg, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.trainers.serializers import (
    TrainerAssignmentSerializer,
    TrainerPerformanceSerializer,
    TrainerScheduleSerializer,
    TrainerSerializer,
)
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import Trainer, TrainerSchedule


class TrainerViewSet(viewsets.ModelViewSet):
    """Tenant-scoped trainer management.

    ``users.Trainer`` carries its tenant via the linked ``User`` record, so the
    queryset is scoped through ``user__tenant`` rather than a ``for_tenant`` manager.
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_trainer"
    serializer_class = TrainerSerializer
    http_method_names = ["get", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        """Return trainers belonging to the request's tenant."""
        return Trainer.objects.select_related("user").filter(
            user__tenant=self.request.tenant
        ).order_by("-created_at")

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
                "monthly_records": TrainerPerformanceSerializer(
                    records, many=True
                ).data,
            }
        )


class TrainerAssignmentViewSet(viewsets.ModelViewSet):
    """Tenant-scoped branch-level trainer↔customer assignments."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.edit_trainer"
    serializer_class = TrainerAssignmentSerializer
    http_method_names = ["get", "post", "head", "options"]
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

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_trainer"
    serializer_class = TrainerPerformanceSerializer
    filterset_fields = ["trainer", "month"]
    pagination_class = None

    def get_queryset(self):
        """Return performance records belonging to the request's tenant."""
        return TrainerPerformance.objects.for_tenant(self.request.tenant).select_related(
            "trainer__user"
        )

    def perform_create(self, serializer):
        """Create a performance record, scoped to the request's tenant."""
        serializer.save(tenant=self.request.tenant)


class TrainerScheduleViewSet(viewsets.ModelViewSet):
    """Tenant-scoped weekly availability schedules for trainers."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "trainers.view_trainer"
    serializer_class = TrainerScheduleSerializer
    filterset_fields = ["trainer", "day_of_week"]
    pagination_class = None

    def get_queryset(self):
        """Return schedules belonging to the request's tenant."""
        return TrainerSchedule.objects.for_tenant(self.request.tenant).select_related(
            "trainer__user"
        )

    def perform_create(self, serializer):
        """Create a schedule entry, scoped to the request's tenant."""
        serializer.save(tenant=self.request.tenant)
