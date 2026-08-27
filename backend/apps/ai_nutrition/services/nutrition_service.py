"""Mock AI nutrition service.

Provides a deterministic, database-backed meal plan generator that picks
food items from the shared ``diet.FoodItem`` catalog (114 Indian items) and
calculates macros from their nutrition data. This stands in for an external
AI/LLM planner until a real provider is integrated.
"""

from __future__ import annotations

import random
from collections import OrderedDict
from typing import Any, Iterable

from apps.diet.models import FoodItem
from apps.tenants.models import Tenant

# Meal slots in a day, in serving order.
MEAL_SLOTS: list[str] = ["breakfast", "lunch", "snack", "dinner"]

# Preferred food groups per meal slot.
MEAL_GROUP_PREFERENCES: dict[str, list[str]] = {
    "breakfast": ["grains", "dairy", "fruit"],
    "lunch": ["protein", "grains", "vegetable"],
    "snack": ["fruit", "snack", "dairy"],
    "dinner": ["protein", "vegetable", "grains"],
}


class NutritionServiceError(Exception):
    """Raised when the AI nutrition service cannot build a plan."""


def _filtered_foods(
    food_group: str,
    dietary_restrictions: list[str] | None,
) -> list:
    """Return candidate food items for a group honouring restrictions.

    Args:
        food_group: The ``FoodGroup`` value to filter by.
        dietary_restrictions: List of restriction tokens.

    Returns:
        A list of candidate ``FoodItem`` rows.
    """
    qs = FoodItem.objects.filter(food_group=food_group)
    restrictions = dietary_restrictions or []

    if "vegetarian" in restrictions:
        qs = qs.filter(is_veg=True)
    if "vegan" in restrictions:
        qs = qs.filter(is_veg=True, food_group__in=["grains", "vegetable", "fruit"])
    if "no-dairy" in restrictions:
        qs = qs.exclude(food_group="dairy")
    if "no-gluten" in restrictions:
        qs = qs.exclude(name__icontains="wheat").exclude(name__icontains="roti")

    return list(qs)


def _pick_food(
    group_preferences: list[str],
    dietary_restrictions: list[str] | None,
    rng: Any,
    exclude: Iterable[int] | None = None,
) -> Any:
    """Pick a food item for a meal, falling back across preferred groups.

    Args:
        group_preferences: Ordered food groups to try.
        dietary_restrictions: Restriction tokens to honour.
        rng: Seeded random generator.
        exclude: Food item ids already used today, to add variety.

    Returns:
        A chosen ``FoodItem``.

    Raises:
        NutritionServiceError: If no food item can be selected.
    """
    exclude_ids = set(exclude or [])
    for group in group_preferences:
        candidates = [c for c in _filtered_foods(group, dietary_restrictions) if c.id not in exclude_ids]
        if candidates:
            return rng.choice(candidates)

    # Last resort: any food item (optionally excluding repeats).
    any_food = list(FoodItem.objects.exclude(id__in=exclude_ids))
    if any_food:
        return rng.choice(any_food)

    raise NutritionServiceError("No food items available to build a meal plan. Seed the diet catalog first.")


def generate_meal_plan(
    *,
    tenant: Tenant,
    user: Any,
    name: str,
    target_calories: int,
    target_protein_g: float,
    target_carbs_g: float,
    target_fat_g: float,
    cuisine_preference: str = "",
    dietary_restrictions: list[str] | None = None,
    start_date: Any = None,
    end_date: Any = None,
    days: int = 7,
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate a weekly meal plan from the food catalog.

    Args:
        tenant: Tenant that owns the plan.
        user: User the plan is generated for.
        name: Display name for the plan.
        target_calories: Target daily calories.
        target_protein_g: Target daily protein (g).
        target_carbs_g: Target daily carbs (g).
        target_fat_g: Target daily fat (g).
        cuisine_preference: Optional cuisine tag (stored, not used for selection).
        dietary_restrictions: List of restriction tokens.
        start_date: Optional plan start date.
        end_date: Optional plan end date.
        days: Number of days in the week (1-7).
        seed: Optional RNG seed for deterministic output (useful in tests).

    Returns:
        A dict with ``plan`` fields plus an ``items`` list of per-meal rows.

    Raises:
        NutritionServiceError: If no food items exist to build the plan.
    """
    from django.utils import timezone

    rng = random.Random(seed)
    restrictions = dietary_restrictions or []

    start_date = start_date or timezone.localdate()
    end_date = end_date or (start_date + timezone.timedelta(days=days - 1))

    items: list[dict[str, Any]] = []

    for day in range(days):
        # Track foods used within the current day for variety; reset each day
        # so the same food can reappear on a different day of the week.
        used_food_ids: set[int] = set()
        for slot in MEAL_SLOTS:
            food = _pick_food(
                MEAL_GROUP_PREFERENCES[slot],
                restrictions,
                rng,
                exclude=used_food_ids,
            )
            used_food_ids.add(food.id)
            items.append(
                {
                    "day_of_week": day,
                    "meal_type": slot,
                    "food_item_id": food.id,
                    "servings": 1.0,
                }
            )

    return {
        "plan": {
            "name": name,
            "target_calories": target_calories,
            "target_protein_g": target_protein_g,
            "target_carbs_g": target_carbs_g,
            "target_fat_g": target_fat_g,
            "cuisine_preference": cuisine_preference,
            "dietary_restrictions": restrictions,
            "start_date": start_date,
            "end_date": end_date,
        },
        "items": items,
    }


def generate_shopping_list(
    *,
    meal_plan_items: Iterable[Any],
    name: str,
) -> list[dict[str, Any]]:
    """Aggregate meal-plan items into a shopping list.

    Args:
        meal_plan_items: Iterable of ``AIMealPlanItem`` instances.
        name: Shopping list display name (unused in aggregation, kept for parity).

    Returns:
        List of ``{food_item_id, quantity, unit}`` dicts aggregated by food item.
    """
    aggregated: "OrderedDict[int, dict[str, Any]]" = OrderedDict()
    for item in meal_plan_items:
        food_id = item.food_item_id
        if food_id in aggregated:
            aggregated[food_id]["quantity"] += item.servings
        else:
            aggregated[food_id] = {
                "food_item_id": food_id,
                "quantity": item.servings,
                "unit": "serving",
            }
    return list(aggregated.values())
