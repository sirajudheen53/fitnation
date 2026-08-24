"""Diet Plan management API views."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.diet.models import (
    DietAssignment,
    DietDay,
    DietMeal,
    DietPlan,
    FoodItem,
)
from apps.diet.serializers import (
    DietAssignmentSerializer,
    DietDayWriteSerializer,
    DietMealNestedSerializer,
    DietMealSerializer,
    DietPlanSerializer,
    FoodItemSerializer,
    NutritionBreakdownSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


# Map write HTTP methods to diet permissions for request-time checks.
# RolePermission reads ``view.method_permissions`` *before* the view method body
# runs, so writes are correctly denied for customers.
_METHOD_PERMISSIONS: dict[str, str] = {
    "POST": "diets.create_diet",
    "PUT": "diets.edit_diet",
    "PATCH": "diets.edit_diet",
    "DELETE": "diets.edit_diet",
}


class DietRolePermission(RolePermission):
    """Role permission that lets customers access their assigned diet data.

    Extends ``RolePermission`` so that, at object level, a customer can retrieve
    a diet plan they are assigned to, the days/meals of such a plan, and their
    own diet assignments — even though these objects do not carry a
    ``customer_id`` foreign key themselves.
    """

    def has_object_permission(self, request: object, view: object, obj: object) -> bool:
        """Authorize object access, allowing customers access to assigned diets.

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

        # Customers may only access diet data tied to their own assignment.
        return self._customer_owns_diet_object(request, obj)

    @staticmethod
    def _customer_owns_diet_object(request: object, obj: object) -> bool:
        """Return whether the customer can access the diet object.

        Args:
            request: The incoming DRF request.
            obj: The diet model instance.

        Returns:
            ``True`` when the object belongs to an active assignment for the
            requesting customer, otherwise ``False``.
        """
        profile = getattr(request.user, "customer_profile", None)
        if profile is None:
            return False

        # DietAssignment: the customer owns their own assignment record.
        if isinstance(obj, DietAssignment):
            return obj.customer_id == profile.id

        if isinstance(obj, DietPlan):
            return DietAssignment.objects.filter(
                tenant=obj.tenant,
                customer_id=profile.id,
                diet_plan_id=obj.id,
                is_active=True,
            ).exists()

        if isinstance(obj, DietDay):
            return DietAssignment.objects.filter(
                tenant=obj.tenant_id,
                customer_id=profile.id,
                diet_plan_id=obj.diet_plan_id,
                is_active=True,
            ).exists()

        if isinstance(obj, DietMeal):
            return DietAssignment.objects.filter(
                tenant=obj.tenant_id,
                customer_id=profile.id,
                diet_plan_id=obj.diet_day.diet_plan_id,
                is_active=True,
            ).exists()

        return False


class FoodItemViewSet(ModelViewSet):
    """CRUD for the global food catalog with search and filters."""

    permission_classes = [IsAuthenticated]
    required_permission = "diets.view_diet"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = FoodItemSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "calories", "protein", "carbs", "fat"]
    ordering = ["name"]
    queryset = FoodItem.objects.all()

    def get_queryset(self) -> FoodItem:
        """Return food items filtered by food_group and is_veg query params."""
        queryset = FoodItem.objects.all()
        food_group = self.request.query_params.get("food_group")
        if food_group:
            queryset = queryset.filter(food_group=food_group)
        is_veg = self.request.query_params.get("is_veg")
        if is_veg is not None and is_veg.lower() in {"true", "false", "1", "0"}:
            queryset = queryset.filter(
                is_veg=is_veg.lower() in {"true", "1"},
            )
        return queryset

    def get_permissions(self) -> list:
        """Return read permissions for all, edit permissions for staff roles."""
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsTenantMember(), DietRolePermission()]
        return [IsAuthenticated()]

    def create(self, request: Request) -> Response:
        """Create a food item."""
        self.required_permission = "diets.create_diet"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        food = serializer.save()
        return Response(
            FoodItemSerializer(food).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a food item."""
        self.required_permission = "diets.edit_diet"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a food item."""
        self.required_permission = "diets.edit_diet"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a food item."""
        self.required_permission = "diets.edit_diet"
        return super().destroy(request, *args, **kwargs)


class DietPlanViewSet(ModelViewSet):
    """Tenant-scoped CRUD for diet plans with nested days/meals."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, DietRolePermission]
    required_permission = "diets.view_diet"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = DietPlanSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "goal", "daily_calories", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self) -> DietPlan:
        """Return diet plans scoped to the request tenant with goal filter."""
        queryset = DietPlan.objects.for_tenant(self.request.tenant)
        goal = self.request.query_params.get("goal")
        if goal:
            queryset = queryset.filter(goal=goal)
        is_template = self.request.query_params.get("is_template")
        if is_template is not None and is_template.lower() in {"true", "false", "1", "0"}:
            queryset = queryset.filter(
                is_template=is_template.lower() in {"true", "1"},
            )
        return queryset

    def perform_create(self, serializer: DietPlanSerializer) -> None:
        """Persist a diet plan within the request tenant."""
        serializer.save()

    def create(self, request: Request) -> Response:
        """Create a diet plan (optionally with nested days and meals)."""
        self.required_permission = "diets.create_diet"
        return super().create(request)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a diet plan."""
        self.required_permission = "diets.edit_diet"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a diet plan."""
        self.required_permission = "diets.edit_diet"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a diet plan."""
        self.required_permission = "diets.edit_diet"
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request: Request, pk: int) -> Response:
        """Duplicate an existing diet plan as a new plan (template copy).

        The copy inherits days and meals, marked ``is_template=True`` unless the
        ``is_template`` query parameter is explicitly provided.
        """
        self.required_permission = "diets.create_diet"
        source = get_object_or_404(
            DietPlan.objects.for_tenant(request.tenant),
            id=pk,
        )
        days = source.days.prefetch_related("meals__food_item").all()

        new_plan = DietPlan.objects.create(
            tenant=request.tenant,
            name=f"{source.name} (copy)",
            description=source.description,
            goal=source.goal,
            daily_calories=source.daily_calories,
            protein_ratio=source.protein_ratio,
            carb_ratio=source.carb_ratio,
            fat_ratio=source.fat_ratio,
            duration_days=source.duration_days,
            is_template=True,
        )

        for day in days:
            new_day = DietDay.objects.create(
                tenant=request.tenant,
                diet_plan=new_plan,
                day_number=day.day_number,
                notes=day.notes,
            )
            for meal in day.meals.all():
                DietMeal.objects.create(
                    tenant=request.tenant,
                    diet_day=new_day,
                    meal_type=meal.meal_type,
                    food_item=meal.food_item,
                    quantity=meal.quantity,
                )
            new_day.recalculate()

        return Response(
            DietPlanSerializer(new_plan, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="nutrition-breakdown")
    def nutrition_breakdown(self, request: Request, pk: int) -> Response:
        """Return the daily macro breakdown for a diet plan."""
        plan = get_object_or_404(
            DietPlan.objects.for_tenant(request.tenant),
            id=pk,
        )
        data = self._build_nutrition_breakdown(plan)
        return Response(NutritionBreakdownSerializer(data).data)

    @staticmethod
    def _build_nutrition_breakdown(plan: DietPlan) -> dict:
        """Aggregate macro totals across all meals in the plan."""
        meals = DietMeal.objects.filter(
            diet_day__diet_plan=plan,
        )
        total_calories = sum((m.calories for m in meals), 0.0)
        total_protein = sum((m.protein for m in meals), 0.0)
        total_carbs = sum((m.carbs for m in meals), 0.0)
        total_fat = sum((m.fat for m in meals), 0.0)

        protein_calories = total_protein * 4
        carb_calories = total_carbs * 4
        fat_calories = total_fat * 9

        calorie_basis = total_calories or 1

        days = plan.days.count() or 1

        return {
            "total_calories": round(total_calories, 2),
            "total_protein": round(total_protein, 2),
            "total_carbs": round(total_carbs, 2),
            "total_fat": round(total_fat, 2),
            "protein_calories": round(protein_calories, 2),
            "carb_calories": round(carb_calories, 2),
            "fat_calories": round(fat_calories, 2),
            "protein_grams_per_day": round(total_protein / days, 2),
            "carb_grams_per_day": round(total_carbs / days, 2),
            "fat_grams_per_day": round(total_fat / days, 2),
            "protein_percent": round(protein_calories / calorie_basis * 100, 2),
            "carb_percent": round(carb_calories / calorie_basis * 100, 2),
            "fat_percent": round(fat_calories / calorie_basis * 100, 2),
        }


class DietDayViewSet(ModelViewSet):
    """Tenant-scoped CRUD for diet days (nested under a plan)."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, DietRolePermission]
    required_permission = "diets.view_diet"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = DietDayWriteSerializer
    queryset = DietDay.objects.none()

    def get_queryset(self) -> DietDay:
        """Return diet days scoped to the tenant (optionally by plan)."""
        queryset = DietDay.objects.for_tenant(self.request.tenant)
        plan_id = self.request.query_params.get("diet_plan")
        if plan_id:
            queryset = queryset.filter(diet_plan_id=plan_id)
        return queryset

    def create(self, request: Request) -> Response:
        """Create a diet day."""
        self.required_permission = "diets.create_diet"
        return super().create(request)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a diet day."""
        self.required_permission = "diets.edit_diet"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a diet day."""
        self.required_permission = "diets.edit_diet"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a diet day."""
        self.required_permission = "diets.edit_diet"
        return super().destroy(request, *args, **kwargs)


class DietMealViewSet(ModelViewSet):
    """Tenant-scoped CRUD for diet meals."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, DietRolePermission]
    required_permission = "diets.view_diet"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = DietMealNestedSerializer

    def get_queryset(self) -> DietMeal:
        """Return diet meals scoped to the tenant (optionally by day)."""
        queryset = DietMeal.objects.for_tenant(self.request.tenant)
        day_id = self.request.query_params.get("diet_day")
        if day_id:
            queryset = queryset.filter(diet_day_id=day_id)
        return queryset

    def create(self, request: Request) -> Response:
        """Create a diet meal."""
        self.required_permission = "diets.create_diet"
        day = get_object_or_404(
            DietDay.objects.for_tenant(request.tenant),
            id=request.data.get("diet_day"),
        )
        serializer = self.get_serializer(
            data=request.data,
            context={"diet_day": day},
        )
        serializer.is_valid(raise_exception=True)
        meal = serializer.save()
        return Response(
            DietMealSerializer(meal).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a diet meal."""
        self.required_permission = "diets.edit_diet"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a diet meal."""
        self.required_permission = "diets.edit_diet"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a diet meal."""
        self.required_permission = "diets.edit_diet"
        return super().destroy(request, *args, **kwargs)


class DietAssignmentViewSet(ModelViewSet):
    """Tenant-scoped CRUD for diet assignments to customers."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, DietRolePermission]
    required_permission = "diets.view_diet"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = DietAssignmentSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "start_date"]
    ordering = ["-created_at"]

    def get_queryset(self) -> DietAssignment:
        """Return diet assignments scoped to the tenant with customer filter."""
        queryset = DietAssignment.objects.for_tenant(self.request.tenant)
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        active = self.request.query_params.get("is_active")
        if active is not None and active.lower() in {"true", "false", "1", "0"}:
            queryset = queryset.filter(is_active=active.lower() in {"true", "1"})
        return queryset

    def create(self, request: Request) -> Response:
        """Assign a diet plan to a customer."""
        self.required_permission = "diets.create_diet"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save(
            tenant=request.tenant,
            assigned_by=request.user,
        )
        return Response(
            DietAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a diet assignment."""
        self.required_permission = "diets.edit_diet"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a diet assignment."""
        self.required_permission = "diets.edit_diet"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a diet assignment."""
        self.required_permission = "diets.edit_diet"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request: Request) -> Response:
        """List the active diet assignment(s) for a given customer.

        When no ``customer`` query parameter is supplied and the requesting user is
        a customer, their own active assignment is returned.
        """
        self.required_permission = "diets.view_diet"
        customer_id = request.query_params.get("customer")
        if not customer_id and request.user.role == "customer":
            profile = getattr(request.user, "customer_profile", None)
            customer_id = profile.id if profile else None

        if not customer_id:
            return Response(
                {"detail": "A 'customer' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignments = DietAssignment.objects.for_tenant(request.tenant).filter(
            customer_id=customer_id,
            is_active=True,
        )
        return Response(DietAssignmentSerializer(assignments, many=True).data)
