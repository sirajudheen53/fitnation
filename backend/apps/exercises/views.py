"""Exercise library API views."""

from typing import ClassVar

from django.db.models import Count
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from django_filters.rest_framework import DjangoFilterBackend

from apps.exercises.models import Exercise, ExerciseCategory
from apps.exercises.serializers import (
    ExerciseCategorySerializer,
    ExerciseSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class ExerciseCategoryViewSet(ModelViewSet):
    """Tenant-scoped CRUD for exercise categories (admin/trainer write)."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "exercises.view_exercise"
    method_permissions: ClassVar[dict] = {
        "GET": "exercises.view_exercise",
        "POST": "exercises.edit_exercise",
        "PUT": "exercises.edit_exercise",
        "PATCH": "exercises.edit_exercise",
        "DELETE": "exercises.delete_exercise",
    }
    serializer_class = ExerciseCategorySerializer
    filter_backends: ClassVar[list] = [filters.SearchFilter, filters.OrderingFilter]
    search_fields: ClassVar[list[str]] = ["name", "description", "slug"]
    ordering_fields: ClassVar[list[str]] = ["name", "created_at"]
    ordering: ClassVar[list[str]] = ["name"]

    def get_queryset(self):
        """Return categories scoped to the tenant with exercise counts."""
        return (
            ExerciseCategory.objects.for_tenant(self.request.tenant).annotate(exercise_count=Count("exercises")).all()
        )

    def perform_create(self, serializer) -> None:
        """Persist the new category scoped to the request tenant."""
        serializer.save(tenant=self.request.tenant)
        # Attach exercise_count so the create response includes it.
        instance = serializer.instance
        instance.exercise_count = instance.exercises.count()


class ExerciseViewSet(ModelViewSet):
    """Tenant-scoped CRUD for exercises with filtering and search."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "exercises.view_exercise"
    method_permissions: ClassVar[dict] = {
        "GET": "exercises.view_exercise",
        "POST": "exercises.edit_exercise",
        "PUT": "exercises.edit_exercise",
        "PATCH": "exercises.edit_exercise",
        "DELETE": "exercises.delete_exercise",
    }
    serializer_class = ExerciseSerializer
    filter_backends: ClassVar[list] = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields: ClassVar[list[str]] = ["category", "difficulty"]
    search_fields: ClassVar[list[str]] = ["name", "description", "tips"]
    ordering_fields: ClassVar[list[str]] = ["name", "difficulty", "created_at"]
    ordering: ClassVar[list[str]] = ["name"]

    def get_queryset(self):
        """Return exercises scoped to the tenant with optional filters."""
        queryset = Exercise.objects.for_tenant(self.request.tenant)
        muscle_group = self.request.query_params.get("muscle_group")
        if muscle_group:
            queryset = queryset.filter(muscle_groups__icontains=muscle_group)
        equipment = self.request.query_params.get("equipment_needed")
        if equipment:
            queryset = queryset.filter(equipment_needed__icontains=equipment)
        return queryset

    def perform_create(self, serializer) -> None:
        """Persist the new exercise scoped to the request tenant."""
        serializer.save(tenant=self.request.tenant)
