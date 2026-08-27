"""Attendance API views."""

from typing import ClassVar

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.attendance.models import AttendanceRecord, TrainerAttendance
from apps.attendance.serializers import (
    AttendanceRecordSerializer,
    TrainerAttendanceSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication
from apps.users.models import User

PERIOD_TRUNC = {
    "daily": TruncDate,
    "weekly": TruncWeek,
    "monthly": TruncMonth,
}


def _format_period(value: object) -> str | None:
    """Render a truncation result as an ISO date string.

    ``TruncDate``/``TruncDay`` yield ``date`` objects while ``TruncWeek`` and
    ``TruncMonth`` yield datetimes. Normalize both to ``YYYY-MM-DD``.
    """
    if value is None:
        return None
    return str(value.date()) if hasattr(value, "date") else str(value)


class AttendanceRecordViewSet(ModelViewSet):
    """Tenant-scoped customer attendance CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        IsTenantMember,
        RolePermission,
    ]
    required_permission = "attendance.view_attendance"
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self) -> AttendanceRecord:
        """Return attendance records scoped to the tenant with optional filters.

        Customer-role users see only their own attendance.
        """
        queryset = AttendanceRecord.objects.for_tenant(self.request.tenant)
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(customer__user=self.request.user)
        else:
            date = self.request.query_params.get("date")
            if date:
                queryset = queryset.filter(date=date)
            customer = self.request.query_params.get("customer")
            if customer:
                queryset = queryset.filter(customer_id=customer)
            branch = self.request.query_params.get("branch")
            if branch:
                queryset = queryset.filter(branch_id=branch)
        return queryset

    def create(self, request: Request) -> Response:
        """Log a new attendance record."""
        self.required_permission = "attendance.log_attendance"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(tenant=request.tenant)
        return Response(
            AttendanceRecordSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update an attendance record."""
        self.required_permission = "attendance.edit_attendance"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update an attendance record."""
        self.required_permission = "attendance.edit_attendance"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete an attendance record."""
        self.required_permission = "attendance.edit_attendance"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def reports(self, request: Request) -> Response:
        """Return attendance counts aggregated by period per customer or branch.

        Query params:
            period: ``daily`` (default), ``weekly``, or ``monthly``.
            group_by: ``customer`` (default) or ``branch``.
            date / customer / branch: optional filters applied before aggregation.
        """
        period = request.query_params.get("period", "daily")
        group_by = request.query_params.get("group_by", "customer")

        trunc = PERIOD_TRUNC.get(period)
        if trunc is None:
            return Response(
                {"period": "Must be one of daily, weekly, monthly."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if group_by not in ("customer", "branch"):
            return Response(
                {"group_by": "Must be one of customer, branch."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset()

        if group_by == "branch":
            rows = (
                queryset.annotate(
                    period=trunc("check_in_time"),
                )
                .values("period", "branch")
                .annotate(count=Count("id"))
                .order_by("period")
            )
            payload = [
                {
                    "period": _format_period(row["period"]),
                    "branch": row["branch"],
                    "count": row["count"],
                }
                for row in rows
            ]
        else:
            rows = (
                queryset.annotate(
                    period=trunc("check_in_time"),
                )
                .values("period", "customer")
                .annotate(count=Count("id"))
                .order_by("period")
            )
            payload = [
                {
                    "period": _format_period(row["period"]),
                    "customer": row["customer"],
                    "count": row["count"],
                }
                for row in rows
            ]

        return Response(
            {"period": period, "group_by": group_by, "results": payload}
        )


class TrainerAttendanceViewSet(ModelViewSet):
    """Tenant-scoped trainer attendance CRUD viewset."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        IsTenantMember,
        RolePermission,
    ]
    required_permission = "attendance.view_attendance"
    serializer_class = TrainerAttendanceSerializer

    def get_queryset(self) -> TrainerAttendance:
        """Return trainer attendance scoped to the tenant with optional filters."""
        queryset = TrainerAttendance.objects.for_tenant(self.request.tenant)
        date = self.request.query_params.get("date")
        if date:
            queryset = queryset.filter(date=date)
        trainer = self.request.query_params.get("trainer")
        if trainer:
            queryset = queryset.filter(trainer_id=trainer)
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return queryset

    def create(self, request: Request) -> Response:
        """Log a new trainer attendance record."""
        self.required_permission = "attendance.log_attendance"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(tenant=request.tenant)
        return Response(
            TrainerAttendanceSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a trainer attendance record."""
        self.required_permission = "attendance.edit_attendance"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a trainer attendance record."""
        self.required_permission = "attendance.edit_attendance"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a trainer attendance record."""
        self.required_permission = "attendance.edit_attendance"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def reports(self, request: Request) -> Response:
        """Return trainer attendance counts aggregated per period.

        Query params:
            period: ``daily`` (default), ``weekly``, or ``monthly``.
            trainer / branch / date filters are applied before aggregation.
        """
        period = request.query_params.get("period", "daily")
        trunc = PERIOD_TRUNC.get(period)
        if trunc is None:
            return Response(
                {"period": "Must be one of daily, weekly, monthly."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset()
        rows = (
            queryset.annotate(period=trunc("check_in_time"))
            .values("period", "trainer")
            .annotate(count=Count("id"))
            .order_by("period")
        )
        payload = [
            {
                "period": _format_period(row["period"]),
                "trainer": row["trainer"],
                "count": row["count"],
            }
            for row in rows
        ]
        return Response({"period": period, "results": payload})
