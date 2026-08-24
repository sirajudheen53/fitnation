"""Workout Builder API views."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication
from apps.workouts.models import (
    WorkoutAssignment,
    WorkoutDay,
    WorkoutExercise,
    WorkoutLog,
    WorkoutPlan,
)
from apps.workouts.serializers import (
    WorkoutAssignmentSerializer,
    WorkoutDayWriteSerializer,
    WorkoutExerciseNestedSerializer,
    WorkoutExerciseSerializer,
    WorkoutLogSerializer,
    WorkoutPlanSerializer,
)


# Map write HTTP methods to workout permissions for request-time checks.
_METHOD_PERMISSIONS: dict[str, str] = {
    "POST": "workouts.create_workout",
    "PUT": "workouts.edit_workout",
    "PATCH": "workouts.edit_workout",
    "DELETE": "workouts.edit_workout",
}

# Workout logs are special: customers may log their own workouts, so POST is
# gated on the read permission (which customers hold) and the create body
# enforces that customers only log for their own profile.
_LOG_METHOD_PERMISSIONS: dict[str, str] = {
    "POST": "workouts.view_workout",
    "PUT": "workouts.edit_workout",
    "PATCH": "workouts.edit_workout",
    "DELETE": "workouts.edit_workout",
}


class WorkoutRolePermission(RolePermission):
    """Role permission that lets customers access their assigned workout data.

    Extends ``RolePermission`` so that, at object level, a customer can retrieve
    a workout plan they are assigned to, the days/exercises of such a plan, and
    their own workout assignments and logs.
    """

    def has_object_permission(self, request: object, view: object, obj: object) -> bool:
        """Authorize object access, allowing customers access to assigned workouts.

        Args:
            request: The incoming DRF request.
            view: The view being accessed.
            obj: The model instance being accessed.

        Returns:
            ``True`` if the user may access the object.
        """
        if not request.user.is_authenticated or request.user.is_superuser:
            return True

        # Cross-tenant guard (mirrors RolePermission).
        if hasattr(obj, "tenant_id") and obj.tenant_id != request.user.tenant_id:
            return False

        if request.user.role != "customer":
            return super().has_object_permission(request, view, obj)

        return self._customer_owns_workout_object(request, obj)

    @staticmethod
    def _customer_owns_workout_object(request: object, obj: object) -> bool:
        """Return whether the customer can access the workout object.

        Args:
            request: The incoming DRF request.
            obj: The workout model instance.

        Returns:
            ``True`` when the object belongs to an active assignment for the
            requesting customer, otherwise ``False``.
        """
        profile = getattr(request.user, "customer_profile", None)
        if profile is None:
            return False

        if isinstance(obj, WorkoutAssignment):
            return obj.customer_id == profile.id

        if isinstance(obj, WorkoutLog):
            return obj.customer_id == profile.id

        if isinstance(obj, WorkoutPlan):
            return WorkoutAssignment.objects.filter(
                tenant=obj.tenant,
                customer_id=profile.id,
                workout_plan_id=obj.id,
                is_active=True,
            ).exists()

        if isinstance(obj, WorkoutDay):
            return WorkoutAssignment.objects.filter(
                tenant=obj.tenant_id,
                customer_id=profile.id,
                workout_plan_id=obj.workout_plan_id,
                is_active=True,
            ).exists()

        if isinstance(obj, WorkoutExercise):
            return WorkoutAssignment.objects.filter(
                tenant=obj.tenant_id,
                customer_id=profile.id,
                workout_plan_id=obj.workout_day.workout_plan_id,
                is_active=True,
            ).exists()

        return False


class WorkoutPlanViewSet(ModelViewSet):
    """Tenant-scoped CRUD for workout plans with nested days/exercises."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, WorkoutRolePermission]
    required_permission = "workouts.view_workout"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = WorkoutPlanSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "goal", "difficulty", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self) -> WorkoutPlan:
        """Return workout plans scoped to the tenant with goal/difficulty filters."""
        queryset = WorkoutPlan.objects.for_tenant(self.request.tenant)
        goal = self.request.query_params.get("goal")
        if goal:
            queryset = queryset.filter(goal=goal)
        difficulty = self.request.query_params.get("difficulty")
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        is_template = self.request.query_params.get("is_template")
        if is_template is not None and is_template.lower() in {"true", "false", "1", "0"}:
            queryset = queryset.filter(
                is_template=is_template.lower() in {"true", "1"},
            )
        return queryset

    def create(self, request: Request) -> Response:
        """Create a workout plan (optionally with nested days and exercises)."""
        self.required_permission = "workouts.create_workout"
        return super().create(request)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a workout plan."""
        self.required_permission = "workouts.edit_workout"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a workout plan."""
        self.required_permission = "workouts.edit_workout"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a workout plan."""
        self.required_permission = "workouts.edit_workout"
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request: Request, pk: int) -> Response:
        """Duplicate an existing workout plan as a new plan (template copy).

        The copy inherits days and exercises, marked ``is_template=True`` unless
        the ``is_template`` query parameter is explicitly provided.
        """
        self.required_permission = "workouts.create_workout"
        source = get_object_or_404(
            WorkoutPlan.objects.for_tenant(request.tenant),
            id=pk,
        )
        days = source.days.prefetch_related("exercises__exercise").all()

        new_plan = WorkoutPlan.objects.create(
            tenant=request.tenant,
            name=f"{source.name} (copy)",
            description=source.description,
            goal=source.goal,
            difficulty=source.difficulty,
            duration_weeks=source.duration_weeks,
            is_template=True,
            created_by=request.user,
        )

        for day in days:
            new_day = WorkoutDay.objects.create(
                tenant=request.tenant,
                workout_plan=new_plan,
                day_of_week=day.day_of_week,
                day_number=day.day_number,
                focus=day.focus,
                notes=day.notes,
            )
            for we in day.exercises.all():
                WorkoutExercise.objects.create(
                    tenant=request.tenant,
                    workout_day=new_day,
                    exercise=we.exercise,
                    sets=we.sets,
                    reps=we.reps,
                    rest_seconds=we.rest_seconds,
                    tempo=we.tempo,
                    rpe=we.rpe,
                    notes=we.notes,
                    order=we.order,
                    alternate_exercise=we.alternate_exercise,
                )

        return Response(
            WorkoutPlanSerializer(new_plan, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class WorkoutDayViewSet(ModelViewSet):
    """Tenant-scoped CRUD for workout days (nested under a plan)."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, WorkoutRolePermission]
    required_permission = "workouts.view_workout"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = WorkoutDayWriteSerializer
    queryset = WorkoutDay.objects.none()

    def get_queryset(self) -> WorkoutDay:
        """Return workout days scoped to the tenant (optionally by plan)."""
        queryset = WorkoutDay.objects.for_tenant(self.request.tenant)
        plan_id = self.request.query_params.get("workout_plan")
        if plan_id:
            queryset = queryset.filter(workout_plan_id=plan_id)
        return queryset

    def create(self, request: Request) -> Response:
        """Create a workout day."""
        self.required_permission = "workouts.create_workout"
        return super().create(request)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a workout day."""
        self.required_permission = "workouts.edit_workout"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a workout day."""
        self.required_permission = "workouts.edit_workout"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a workout day."""
        self.required_permission = "workouts.edit_workout"
        return super().destroy(request, *args, **kwargs)


class WorkoutExerciseViewSet(ModelViewSet):
    """Tenant-scoped CRUD for workout exercises."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, WorkoutRolePermission]
    required_permission = "workouts.view_workout"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = WorkoutExerciseNestedSerializer

    def get_queryset(self) -> WorkoutExercise:
        """Return workout exercises scoped to the tenant (optionally by day)."""
        queryset = WorkoutExercise.objects.for_tenant(self.request.tenant)
        day_id = self.request.query_params.get("workout_day")
        if day_id:
            queryset = queryset.filter(workout_day_id=day_id)
        return queryset

    def create(self, request: Request) -> Response:
        """Create a workout exercise."""
        self.required_permission = "workouts.create_workout"
        day = get_object_or_404(
            WorkoutDay.objects.for_tenant(request.tenant),
            id=request.data.get("workout_day"),
        )
        serializer = self.get_serializer(
            data=request.data,
            context={"workout_day": day},
        )
        serializer.is_valid(raise_exception=True)
        we = serializer.save()
        return Response(
            WorkoutExerciseSerializer(we).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a workout exercise."""
        self.required_permission = "workouts.edit_workout"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a workout exercise."""
        self.required_permission = "workouts.edit_workout"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a workout exercise."""
        self.required_permission = "workouts.edit_workout"
        return super().destroy(request, *args, **kwargs)


class WorkoutAssignmentViewSet(ModelViewSet):
    """Tenant-scoped CRUD for workout assignments to customers."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, WorkoutRolePermission]
    required_permission = "workouts.view_workout"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = WorkoutAssignmentSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "start_date"]
    ordering = ["-created_at"]

    def get_queryset(self) -> WorkoutAssignment:
        """Return workout assignments scoped to the tenant with customer filter."""
        queryset = WorkoutAssignment.objects.for_tenant(self.request.tenant)
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        active = self.request.query_params.get("is_active")
        if active is not None and active.lower() in {"true", "false", "1", "0"}:
            queryset = queryset.filter(is_active=active.lower() in {"true", "1"})
        return queryset

    def create(self, request: Request) -> Response:
        """Assign a workout plan to a customer."""
        self.required_permission = "workouts.create_workout"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save(
            tenant=request.tenant,
            assigned_by=request.user,
        )
        return Response(
            WorkoutAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a workout assignment."""
        self.required_permission = "workouts.edit_workout"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a workout assignment."""
        self.required_permission = "workouts.edit_workout"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a workout assignment."""
        self.required_permission = "workouts.edit_workout"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request: Request) -> Response:
        """List the active workout assignment(s) for a given customer.

        When no ``customer`` query parameter is supplied and the requesting user is
        a customer, their own active assignment is returned.
        """
        self.required_permission = "workouts.view_workout"
        customer_id = request.query_params.get("customer")
        if not customer_id and request.user.role == "customer":
            profile = getattr(request.user, "customer_profile", None)
            customer_id = profile.id if profile else None

        if not customer_id:
            return Response(
                {"detail": "A 'customer' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignments = WorkoutAssignment.objects.for_tenant(request.tenant).filter(
            customer_id=customer_id,
            is_active=True,
        )
        return Response(WorkoutAssignmentSerializer(assignments, many=True).data)


class WorkoutLogViewSet(ModelViewSet):
    """Tenant-scoped CRUD for workout logs and progress tracking."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, WorkoutRolePermission]
    required_permission = "workouts.view_workout"
    method_permissions = _LOG_METHOD_PERMISSIONS
    serializer_class = WorkoutLogSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["date_completed", "created_at"]
    ordering = ["-date_completed"]

    def get_queryset(self) -> WorkoutLog:
        """Return workout logs scoped to the tenant with customer/date filters."""
        queryset = WorkoutLog.objects.for_tenant(self.request.tenant)
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(date_completed__gte=date_from)
        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(date_completed__lte=date_to)
        return queryset

    def create(self, request: Request) -> Response:
        """Log a workout set for a customer.

        Customers may log their own workout sets; staff roles may log for any
        customer in the tenant.
        """
        if request.user.role == "customer":
            profile = getattr(request.user, "customer_profile", None)
            submitted_customer = request.data.get("customer")
            if profile is None or int(submitted_customer) != profile.id:
                return Response(
                    {"detail": "Customers may only log their own workouts."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(tenant=request.tenant)
        return Response(
            WorkoutLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a workout log."""
        self.required_permission = "workouts.edit_workout"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a workout log."""
        self.required_permission = "workouts.edit_workout"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a workout log."""
        self.required_permission = "workouts.edit_workout"
        return super().destroy(request, *args, **kwargs)
