"""Diet Plan management serializers."""

from rest_framework import serializers

from apps.diet.models import (
    DietAssignment,
    DietDay,
    DietMeal,
    DietPlan,
    FoodItem,
)


class FoodItemSerializer(serializers.ModelSerializer):
    """Serialize a global food catalog item."""

    class Meta:
        """Serializer metadata."""

        model = FoodItem
        fields = [
            "id",
            "name",
            "serving_size",
            "calories",
            "protein",
            "carbs",
            "fat",
            "fiber",
            "glycemic_index",
            "food_group",
            "is_veg",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class DietMealSerializer(serializers.ModelSerializer):
    """Serialize a meal entry with auto-calculated nutrition."""

    food_item_name = serializers.CharField(
        source="food_item.name",
        read_only=True,
    )

    class Meta:
        model = DietMeal
        fields = [
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
        ]
        read_only_fields = ["id", "calories", "protein", "carbs", "fat"]
        extra_kwargs = {"diet_day": {"required": False}}

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
        read_only_fields = [
            "id",
            "calories",
            "protein",
            "carbs",
            "fat",
        ]
        extra_kwargs = {
            "food_item": {"required": True},
            "diet_day": {"required": False},
        }


class DietDaySerializer(serializers.ModelSerializer):
    """Serialize a diet day with nested meals."""

    meals = DietMealSerializer(many=True, required=False)

    class Meta:
        model = DietDay
        fields = [
            "id",
            "diet_plan",
            "day_number",
            "total_calories",
            "notes",
            "meals",
        ]
        read_only_fields = ["id", "diet_plan", "total_calories"]

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
        fields = [
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
        read_only_fields = ["id", "created_at", "updated_at"]

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
        read_only_fields = ["id", "total_calories"]


class DietAssignmentSerializer(serializers.ModelSerializer):
    """Serialize a diet plan assignment to a customer."""

    diet_plan_name = serializers.CharField(
        source="diet_plan.name",
        read_only=True,
    )
    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )

    class Meta:
        model = DietAssignment
        fields = [
            "id",
            "customer",
            "diet_plan",
            "diet_plan_name",
            "customer_name",
            "start_date",
            "end_date",
            "is_active",
            "assigned_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "assigned_by", "created_at", "updated_at"]


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
