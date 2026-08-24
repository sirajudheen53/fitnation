"""AI Nutrition Assistant API views."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.ai_nutrition.models import (
    AIMealPlan,
    AIMealPlanItem,
    MacroLog,
    ShoppingList,
    ShoppingListItem,
)
from apps.ai_nutrition.serializers import (
    AIMealPlanReadSerializer,
    AIMealPlanWriteSerializer,
    MacroLogSerializer,
    ShoppingListSerializer,
)
from apps.ai_nutrition.services.nutrition_service import (
    NutritionServiceError,
    generate_meal_plan,
    generate_shopping_list,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


_METHOD_PERMISSIONS: dict[str, str] = {
    "POST": "ai_nutrition.create",
    "PUT": "ai_nutrition.edit",
    "PATCH": "ai_nutrition.edit",
    "DELETE": "ai_nutrition.edit",
}


class AINutritionRole(RolePermission):
    """Role permission that lets customers access their own AI nutrition data.

    Extends ``RolePermission``: object-level checks already allow a customer to
    access any object carrying their ``user_id``, which all AI nutrition models do.
    This subclass exists for clarity and future per-model refinement.
    """


class AIMealPlanViewSet(ModelViewSet):
    """Tenant-scoped CRUD for AI meal plans, with AI generation on create."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, AINutritionRole]
    required_permission = "ai_nutrition.view"
    method_permissions = _METHOD_PERMISSIONS
    filter_backends = []

    def get_serializer_class(self):
        """Return the write serializer for creation, read otherwise."""
        if self.action in ("create", "update", "partial_update"):
            return AIMealPlanWriteSerializer
        return AIMealPlanReadSerializer

    def get_queryset(self):
        """Return meal plans scoped to the request tenant (optionally by user)."""
        queryset = AIMealPlan.objects.for_tenant(self.request.tenant)
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer) -> None:
        """Generate an AI meal plan and persist it with its items."""
        serializer.save(
            tenant=self.request.tenant,
            user=self.request.user,
        )

    def create(self, request: Request) -> Response:
        """Generate a new AI meal plan based on the request preferences."""
        self.required_permission = "ai_nutrition.create"
        serializer = AIMealPlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        days = data.pop("days", 7)

        try:
            generated = generate_meal_plan(
                tenant=self.request.tenant,
                user=self.request.user,
                name=data.get("name", "My Meal Plan"),
                target_calories=data.get("target_calories", 0),
                target_protein_g=data.get("target_protein_g", 0),
                target_carbs_g=data.get("target_carbs_g", 0),
                target_fat_g=data.get("target_fat_g", 0),
                cuisine_preference=data.get("cuisine_preference", ""),
                dietary_restrictions=data.get("dietary_restrictions", []),
                start_date=data.get("start_date"),
                end_date=data.get("end_date"),
                days=days,
            )
        except NutritionServiceError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = AIMealPlan.objects.create(
            tenant=self.request.tenant,
            user=self.request.user,
            **generated["plan"],
        )
        for item in generated["items"]:
            AIMealPlanItem.objects.create(
                tenant=self.request.tenant,
                meal_plan=plan,
                **item,
            )

        return Response(
            AIMealPlanReadSerializer(
                plan, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a meal plan."""
        self.required_permission = "ai_nutrition.edit"
        return super().update(request, *args, **kwargs)

    def partial_update(
        self,
        request: Request,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Partially update a meal plan."""
        self.required_permission = "ai_nutrition.edit"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a meal plan."""
        self.required_permission = "ai_nutrition.edit"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request: Request) -> Response:
        """Alias endpoint: generate a new meal plan."""
        return self.create(request)


class ShoppingListViewSet(ModelViewSet):
    """Tenant-scoped CRUD for shopping lists, generated from a meal plan."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, AINutritionRole]
    required_permission = "ai_nutrition.view"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = ShoppingListSerializer
    filter_backends = []

    def get_queryset(self):
        """Return shopping lists scoped to the tenant (optionally by user)."""
        queryset = ShoppingList.objects.for_tenant(self.request.tenant)
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

    def create(self, request: Request) -> Response:
        """Generate a shopping list from a meal plan."""
        self.required_permission = "ai_nutrition.create"
        meal_plan_id = request.data.get("meal_plan")
        if not meal_plan_id:
            return Response(
                {"detail": "A 'meal_plan' is required to generate a shopping list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = get_object_or_404(
            AIMealPlan.objects.for_tenant(self.request.tenant),
            id=meal_plan_id,
        )

        list_name = request.data.get("name", f"Shopping List — {plan.name}")
        shopping_list = ShoppingList.objects.create(
            tenant=self.request.tenant,
            user=self.request.user,
            meal_plan=plan,
            name=list_name,
        )

        entries = generate_shopping_list(
            meal_plan_items=plan.items.all(),
            name=list_name,
        )
        for entry in entries:
            ShoppingListItem.objects.create(
                tenant=self.request.tenant,
                shopping_list=shopping_list,
                food_item_id=entry["food_item_id"],
                quantity=entry["quantity"],
                unit=entry["unit"],
            )

        return Response(
            ShoppingListSerializer(
                shopping_list, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Partially update a shopping list (e.g. mark items purchased)."""
        self.required_permission = "ai_nutrition.edit"

        # Allow marking individual items as purchased via the request body.
        purchased_items = request.data.get("purchased_items")
        if isinstance(purchased_items, list):
            instance = self.get_object()
            item_ids = [int(i) for i in purchased_items if str(i).isdigit()]
            ShoppingListItem.objects.filter(
                shopping_list=instance,
                id__in=item_ids,
            ).update(is_purchased=True)

        return super().partial_update(request, *args, **kwargs)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a shopping list."""
        self.required_permission = "ai_nutrition.edit"
        return super().update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a shopping list."""
        self.required_permission = "ai_nutrition.edit"
        return super().destroy(request, *args, **kwargs)


class MacroLogViewSet(ModelViewSet):
    """Tenant-scoped CRUD for daily macro logs, with weekly/monthly trends."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, AINutritionRole]
    required_permission = "ai_nutrition.view"
    method_permissions = _METHOD_PERMISSIONS
    serializer_class = MacroLogSerializer
    filter_backends = []

    def get_queryset(self):
        """Return macro logs scoped to the tenant (optionally by user/date)."""
        queryset = MacroLog.objects.for_tenant(self.request.tenant)
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        date = self.request.query_params.get("date")
        if date:
            queryset = queryset.filter(date=date)
        return queryset

    def perform_create(self, serializer) -> None:
        """Persist a macro log for the requesting user."""
        serializer.save(
            tenant=self.request.tenant,
            user=self.request.user,
        )

    def create(self, request: Request) -> Response:
        """Log daily food intake."""
        self.required_permission = "ai_nutrition.create"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(tenant=self.request.tenant, user=self.request.user)
        return Response(
            MacroLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Partially update a macro log."""
        self.required_permission = "ai_nutrition.edit"
        return super().partial_update(request, *args, **kwargs)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Update a macro log."""
        self.required_permission = "ai_nutrition.edit"
        return super().update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Delete a macro log."""
        self.required_permission = "ai_nutrition.edit"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="trend")
    def trend(self, request: Request) -> Response:
        """Return weekly or monthly aggregate macro trends for the user."""
        self.required_permission = "ai_nutrition.view"
        period = request.query_params.get("period", "weekly")
        user_id = request.query_params.get("user")

        logs = self.get_queryset()
        if user_id:
            logs = logs.filter(user_id=user_id)

        if not logs.exists():
            return Response(
                {
                    "period": period,
                    "buckets": [],
                    "averages": {
                        "calories_consumed": 0,
                        "protein_consumed_g": 0,
                        "carbs_consumed_g": 0,
                        "fat_consumed_g": 0,
                        "water_intake_ml": 0,
                    },
                }
            )

        from django.db.models import Avg, Sum

        aggregation = logs.values("date").aggregate(
            calories=Sum("calories_consumed"),
            protein=Sum("protein_consumed_g"),
            carbs=Sum("carbs_consumed_g"),
            fat=Sum("fat_consumed_g"),
            water=Sum("water_intake_ml"),
        )
        count = logs.values("date").distinct().count() or 1

        return Response(
            {
                "period": period,
                "buckets": list(
                    logs.values("date").annotate(
                        calories=Sum("calories_consumed"),
                        protein=Sum("protein_consumed_g"),
                        carbs=Sum("carbs_consumed_g"),
                        fat=Sum("fat_consumed_g"),
                        water=Sum("water_intake_ml"),
                    )
                ),
                "averages": {
                    "calories_consumed": round((aggregation["calories"] or 0) / count, 2),
                    "protein_consumed_g": round((aggregation["protein"] or 0) / count, 2),
                    "carbs_consumed_g": round((aggregation["carbs"] or 0) / count, 2),
                    "fat_consumed_g": round((aggregation["fat"] or 0) / count, 2),
                    "water_intake_ml": round((aggregation["water"] or 0) / count, 2),
                },
            }
        )
