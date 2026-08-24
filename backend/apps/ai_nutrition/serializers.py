"""AI Nutrition serializers."""

from rest_framework import serializers

from apps.ai_nutrition.models import (
    AIMealPlan,
    AIMealPlanItem,
    MacroLog,
    ShoppingList,
    ShoppingListItem,
)
from apps.diet.models import FoodItem


class FoodItemBriefSerializer(serializers.ModelSerializer):
    """Brief read-only view of a food item used in nested output."""

    class Meta:
        model = FoodItem
        fields = ["id", "name", "serving_size", "calories", "protein", "carbs", "fat"]


class AIMealPlanItemReadSerializer(serializers.ModelSerializer):
    """Read representation of a meal plan item with food details."""

    food_item = FoodItemBriefSerializer(read_only=True)

    class Meta:
        model = AIMealPlanItem
        fields = [
            "id",
            "meal_plan",
            "day_of_week",
            "meal_type",
            "food_item",
            "servings",
            "calories",
            "protein_g",
            "carbs_g",
            "fat_g",
            "created_at",
        ]
        read_only_fields = ["id", "meal_plan", "created_at"]


class AIMealPlanWriteSerializer(serializers.ModelSerializer):
    """Write representation of a meal plan (generation input)."""

    days = serializers.IntegerField(
        min_value=1,
        max_value=7,
        default=7,
        write_only=True,
    )

    class Meta:
        model = AIMealPlan
        fields = [
            "id",
            "uuid",
            "name",
            "target_calories",
            "target_protein_g",
            "target_carbs_g",
            "target_fat_g",
            "cuisine_preference",
            "dietary_restrictions",
            "start_date",
            "end_date",
            "status",
            "days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "created_at", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        """Ensure end_date (if provided) is not before start_date."""
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "end_date cannot be before start_date."}
            )
        return attrs


class AIMealPlanReadSerializer(serializers.ModelSerializer):
    """Read representation of a meal plan with nested items."""

    items = AIMealPlanItemReadSerializer(many=True, read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = AIMealPlan
        fields = [
            "id",
            "uuid",
            "user",
            "user_email",
            "name",
            "target_calories",
            "target_protein_g",
            "target_carbs_g",
            "target_fat_g",
            "cuisine_preference",
            "dietary_restrictions",
            "start_date",
            "end_date",
            "status",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ShoppingListItemSerializer(serializers.ModelSerializer):
    """Serializer for a shopping list item with food details."""

    food_item = FoodItemBriefSerializer(read_only=True)

    class Meta:
        model = ShoppingListItem
        fields = [
            "id",
            "shopping_list",
            "food_item",
            "quantity",
            "unit",
            "is_purchased",
            "created_at",
        ]
        read_only_fields = ["id", "shopping_list", "food_item", "quantity", "unit", "created_at"]
        extra_kwargs = {
            "shopping_list": {"required": False},
            "food_item": {"required": False},
        }


class ShoppingListSerializer(serializers.ModelSerializer):
    """Serializer for a shopping list with nested items."""

    items = ShoppingListItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShoppingList
        fields = ["id", "user", "meal_plan", "name", "status", "items", "created_at"]
        read_only_fields = ["id", "user", "meal_plan", "created_at"]


class MacroLogSerializer(serializers.ModelSerializer):
    """Serializer for daily macro logs."""

    class Meta:
        model = MacroLog
        fields = [
            "id",
            "user",
            "date",
            "calories_consumed",
            "protein_consumed_g",
            "carbs_consumed_g",
            "fat_consumed_g",
            "water_intake_ml",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]
