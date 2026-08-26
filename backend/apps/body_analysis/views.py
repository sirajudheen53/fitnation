"""AI body analysis API views."""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.body_analysis.models import BodyAnalysis, BodyPhoto, BodyProgressLog
from apps.body_analysis.serializers import (
    BodyAnalysisSerializer,
    BodyPhotoSerializer,
    BodyPhotoUploadSerializer,
    BodyProgressLogSerializer,
    BodyProgressTrendSerializer,
)
from apps.body_analysis.services import build_progress_trend, create_photo_for_analysis
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class BodyAnalysisViewSet(ModelViewSet):
    """Tenant-scoped CRUD for body analysis sessions."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "body_analysis.view_bodyanalysis"
    serializer_class = BodyAnalysisSerializer
    lookup_field = "pk"

    def get_queryset(self) -> BodyAnalysis:
        """Return analyses scoped to the request tenant, optionally by user."""
        queryset = BodyAnalysis.objects.for_tenant(self.request.tenant)
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=user)
        return queryset

    def create(self, request: Request) -> Response:
        """Create a new body analysis session."""
        self.required_permission = "body_analysis.create_bodyanalysis"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis = serializer.save(tenant=request.tenant)
        return Response(
            self.get_serializer(analysis).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a body analysis session."""
        self.required_permission = "body_analysis.edit_bodyanalysis"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a body analysis session."""
        self.required_permission = "body_analysis.edit_bodyanalysis"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a body analysis session."""
        self.required_permission = "body_analysis.delete_bodyanalysis"
        return super().destroy(request, *args, **kwargs)


class BodyPhotoUploadViewSet(GenericViewSet):
    """Handle multipart body-photo uploads."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "body_analysis.create_bodyphoto"
    serializer_class = BodyPhotoUploadSerializer
    queryset = BodyPhoto.objects.none()

    def create(self, request: Request) -> Response:
        """Accept a multipart upload and attach the photo to an analysis."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        try:
            photo = create_photo_for_analysis(
                tenant=request.tenant,
                analysis_id=validated["analysis_id"],
                photo_type=validated["photo_type"],
                image_url=validated.get("image_url", ""),
            )
        except BodyAnalysis.DoesNotExist:
            return Response(
                {"detail": "Body analysis not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            BodyPhotoSerializer(photo).data,
            status=status.HTTP_201_CREATED,
        )


class BodyProgressLogViewSet(ModelViewSet):
    """Tenant-scoped CRUD for body progress logs."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "body_analysis.view_bodyprogresslog"
    serializer_class = BodyProgressLogSerializer

    def get_queryset(self) -> BodyProgressLog:
        """Return progress logs scoped to tenant, optionally filtered by user/metric."""
        queryset = BodyProgressLog.objects.for_tenant(self.request.tenant)
        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_id=user)
        metric = self.request.query_params.get("metric_type")
        if metric:
            queryset = queryset.filter(metric_type=metric)
        return queryset

    def create(self, request: Request) -> Response:
        """Log a new measurement."""
        self.required_permission = "body_analysis.create_bodyprogresslog"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(tenant=request.tenant)
        return Response(
            self.get_serializer(log).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a progress log."""
        self.required_permission = "body_analysis.edit_bodyprogresslog"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a progress log."""
        self.required_permission = "body_analysis.edit_bodyprogresslog"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a progress log."""
        self.required_permission = "body_analysis.delete_bodyprogresslog"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="trend")
    def trend(self, request: Request) -> Response:
        """Return time-series data for charting a single metric."""
        self.required_permission = "body_analysis.view_bodyprogresslog"
        metric_type = request.query_params.get("metric_type")
        if not metric_type:
            return Response(
                {"detail": "metric_type query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if metric_type not in BodyProgressLog.MetricType.values:
            return Response(
                {"detail": "Invalid metric_type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = request.query_params.get("user") or request.user.id
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        data = build_progress_trend(
            tenant=request.tenant,
            user_id=user_id,
            metric_type=metric_type,
            start_date=start_date or None,
            end_date=end_date or None,
        )
        return Response(BodyProgressTrendSerializer(data, many=True).data)
