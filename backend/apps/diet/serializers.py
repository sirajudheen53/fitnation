"""Diet Plan management serializers."""

from datetime import timedelta
from typing import ClassVar

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.customers.serializers import DeletedCustomerFlagMixin
from apps.diet.models import (
    DietAssignment,
    DietDay,
    DietMeal,
    DietPlan,
    FoodItem,
)


class VisibleFoodItemField(serializers.PrimaryKeyRelatedField):
    """Food-item FK limited to the global catalogue plus the request tenant.

    Prevents diet meals from referencing another tenant's custom dishes while
    keeping every global catalogue entry selectable.
    """

    def get_queryset(self) -> FoodItem:
        """Return visible food items for the requesting tenant.

        Returns:
            Queryset of global items plus the request tenant's customs; global
            only when no tenant is resolvable from the request.
        """
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        return FoodItem.visible_to(tenant)


class FoodItemSerializer(serializers.ModelSerializer):
    """Serialize a global or tenant-custom food catalog item."""

    tenant = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)

    class Meta:
        """Serializer metadata."""

        model = FoodItem
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "tenant",
            "serving_size",
            "calories",
            "protein",
            "carbs",
            "fat",
            "fiber",
            "glycemic_index",
            "food_group",
            "meal_type",
            "is_dish",
            "is_veg",
            "created_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "tenant", "created_at"]

    def validate_name(self, value: str) -> str:
        """Reject names colliding within the caller's visible catalogue.

        The check is case-insensitive and covers global entries plus the
        request tenant's custom dishes; on update the instance itself is
        excluded.

        Args:
            value: The submitted item name.

        Returns:
            The trimmed name.

        Raises:
            serializers.ValidationError: If the name already exists in scope.
        """
        name = value.strip()
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        queryset = FoodItem.visible_to(tenant).filter(name__iexact=name)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "A food item or dish with this name already exists.",
            )
        return name


class DietMealSerializer(serializers.ModelSerializer):
    """Serialize a meal entry with auto-calculated nutrition."""

    food_item = VisibleFoodItemField()
    food_item_name = serializers.CharField(
        source="food_item.name",
        read_only=True,
    )

    class Meta:
        model = DietMeal
        fields: ClassVar[list[str]] = [
            "id",
            "diet_day",
            "meal_type",
            "food_item",
            "food_item_name",
            "quantity",
            "calories",
            "protein",
            "carbs",
            "fat",
            "is_completed",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "calories", "protein", "carbs", "fat"]
        extra_kwargs: ClassVar[dict] = {"diet_day": {"required": False}}

    def validate_quantity(self, value: float) -> float:
        """Ensure quantity is a positive number."""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def create(self, validated_data: dict) -> DietMeal:
        """Create a meal, injecting the parent day and tenant."""
        diet_day = validated_data.pop("diet_day", None)
        if diet_day is None:
            diet_day = self.context["diet_day"]
        meal = DietMeal.objects.create(
            diet_day=diet_day,
            tenant=diet_day.tenant,
            **validated_data,
        )
        return meal

    def update(self, instance: DietMeal, validated_data: dict) -> DietMeal:
        """Update a meal, recalculating nutrition when food or quantity change."""
        instance = super().update(instance, validated_data)
        instance.recalculate()
        return instance


class DietMealNestedSerializer(DietMealSerializer):
    """DietMeal serializer used for nested (read) representation within days."""

    class Meta(DietMealSerializer.Meta):
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "calories",
            "protein",
            "carbs",
            "fat",
        ]
        extra_kwargs: ClassVar[dict] = {
            "food_item": {"required": True},
            "diet_day": {"required": False},
        }


class DietDaySerializer(serializers.ModelSerializer):
    """Serialize a diet day with nested meals."""

    meals = DietMealSerializer(many=True, required=False)

    class Meta:
        model = DietDay
        fields: ClassVar[list[str]] = [
            "id",
            "diet_plan",
            "day_number",
            "total_calories",
            "notes",
            "meals",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "diet_plan", "total_calories"]

    def create(self, validated_data: dict) -> DietDay:
        """Create a day and its nested meals."""
        meals_data = validated_data.pop("meals", [])
        diet_plan = validated_data.pop("diet_plan", None)
        if diet_plan is None:
            diet_plan = self.context["diet_plan"]
        day = DietDay.objects.create(
            diet_plan=diet_plan,
            tenant=diet_plan.tenant,
            **validated_data,
        )
        for meal_data in meals_data:
            meal_data["diet_day"] = day
            DietMeal.objects.create(
                tenant=diet_plan.tenant,
                **meal_data,
            )
        day.recalculate()
        return day

    def update(self, instance: DietDay, validated_data: dict) -> DietDay:
        """Update a diet day, supporting full nested meals replacement."""
        meals_data = validated_data.pop("meals", None)
        instance = super().update(instance, validated_data)

        if meals_data is not None:
            instance.meals.all().delete()
            for meal_data in meals_data:
                DietMeal.objects.create(
                    tenant=instance.tenant,
                    diet_day=instance,
                    **meal_data,
                )
            instance.recalculate()

        return instance


class DietPlanSerializer(serializers.ModelSerializer):
    """Serialize a diet plan with nested days, meals and nutrition totals."""

    days = DietDaySerializer(many=True, required=False)

    class Meta:
        model = DietPlan
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "description",
            "goal",
            "daily_calories",
            "protein_ratio",
            "carb_ratio",
            "fat_ratio",
            "duration_days",
            "is_template",
            "created_at",
            "updated_at",
            "days",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> DietPlan:
        """Create a diet plan with nested days and meals in a single request."""
        days_data = validated_data.pop("days", [])
        plan = DietPlan.objects.create(
            tenant=self.context["request"].tenant,
            **validated_data,
        )
        for day_data in days_data:
            meals_data = day_data.pop("meals", [])
            day = DietDay.objects.create(
                diet_plan=plan,
                tenant=plan.tenant,
                **day_data,
            )
            for meal_data in meals_data:
                DietMeal.objects.create(
                    diet_day=day,
                    tenant=plan.tenant,
                    **meal_data,
                )
            day.recalculate()

        if not plan.daily_calories:
            plan.daily_calories = self._avg_daily_calories(plan)
            plan.save(update_fields=["daily_calories"])
        return plan

    @staticmethod
    def _avg_daily_calories(plan: DietPlan) -> int:
        """Return the average total calories across the plan's days.

        Args:
            plan: The diet plan whose days are aggregated.

        Returns:
            Rounded average daily calorie total, or 0 when there are no days
            with a non-zero total.
        """
        totals = [day.total_calories for day in plan.days.all() if day.total_calories]
        if not totals:
            return 0
        return round(sum(totals) / len(totals))


class DietDayWriteSerializer(DietDaySerializer):
    """Writable diet day used for nested CRUD via the day viewset."""

    diet_plan = serializers.PrimaryKeyRelatedField(
        queryset=DietPlan.objects.all(),
        required=True,
    )

    class Meta(DietDaySerializer.Meta):
        read_only_fields: ClassVar[list[str]] = ["id", "total_calories"]


class DietAssignmentSerializer(DeletedCustomerFlagMixin, serializers.ModelSerializer):
    """Serialize a diet plan assignment to a customer."""

    diet_plan_name = serializers.CharField(
        source="diet_plan.name",
        read_only=True,
    )
    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )
    # Issue #90 replace flow: creating with replace_active=True ends the
    # customer's other active assignment(s) so they hold exactly one current
    # plan. Past assignments are kept as history, never deleted.
    replace_active = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Deactivate the customer's other active assignment(s) on create.",
    )

    class Meta:
        model = DietAssignment
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "diet_plan",
            "diet_plan_name",
            "customer_name",
            "customer_is_deleted",
            "start_date",
            "end_date",
            "is_active",
            "assigned_by",
            "notes",
            "replace_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "assigned_by", "created_at", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        """Reject an end date that falls before the start date."""
        instance = getattr(self, "instance", None)
        start_date = attrs.get("start_date", instance.start_date if instance else None)
        end_date = attrs.get("end_date", instance.end_date if instance else None)
        if start_date is None:
            start_date = timezone.localdate()
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before the start date."},
            )
        return attrs

    def create(self, validated_data: dict) -> DietAssignment:
        """Create the assignment, optionally replacing the current one."""
        replace_active = validated_data.pop("replace_active", False)
        with transaction.atomic():
            assignment = super().create(validated_data)
            if replace_active:
                self._deactivate_other_active(assignment)
        return assignment

    @staticmethod
    def _deactivate_other_active(assignment: DietAssignment) -> None:
        """End the customer's other active assignments, keeping history rows."""
        others = DietAssignment.objects.filter(
            tenant_id=assignment.tenant_id,
            customer_id=assignment.customer_id,
            is_active=True,
        ).exclude(pk=assignment.pk)
        for other in others:
            other.is_active = False
            if other.end_date is None or other.end_date >= assignment.start_date:
                other.end_date = assignment.start_date - timedelta(days=1)
            other.save(update_fields=["is_active", "end_date", "updated_at"])

    def validate_customer(self, value) -> object:
        """Ensure the customer belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The customer does not belong to the current tenant.",
            )
        return value

    def validate_diet_plan(self, value: DietPlan) -> DietPlan:
        """Ensure the diet plan belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The diet plan does not belong to the current tenant.",
            )
        return value


class NutritionBreakdownSerializer(serializers.Serializer):
    """Macro breakdown response for a diet plan."""

    total_calories = serializers.FloatField()
    total_protein = serializers.FloatField()
    total_carbs = serializers.FloatField()
    total_fat = serializers.FloatField()
    protein_calories = serializers.FloatField()
    carb_calories = serializers.FloatField()
    fat_calories = serializers.FloatField()
    protein_grams_per_day = serializers.FloatField()
    carb_grams_per_day = serializers.FloatField()
    fat_grams_per_day = serializers.FloatField()
    protein_percent = serializers.FloatField()
    carb_percent = serializers.FloatField()
    fat_percent = serializers.FloatField()
