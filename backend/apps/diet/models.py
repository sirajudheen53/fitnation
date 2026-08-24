"""Diet Plan management models.

Provides a global shared catalog of food items plus tenant-scoped diet plans,
diet days, meals and customer assignments. Nutrition is auto-calculated from
the underlying food item and the serving quantity multiplier.
"""

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin


class FoodItem(models.Model):
    """A global (non-tenant-scoped) food catalog entry with nutrition data.

    Food items are universal — the same rice, dal or egg is nutritionally
    identical across every gym tenant — so they are intentionally shared.
    """

    class FoodGroup(models.TextChoices):
        """Broad food categories used for filtering and planning."""

        GRAINS = "grains", "Grains"
        PROTEIN = "protein", "Protein"
        VEGETABLE = "vegetable", "Vegetable"
        FRUIT = "fruit", "Fruit"
        DAIRY = "dairy", "Dairy"
        FAT = "fat", "Fat"
        SNACK = "snack", "Snack"
        BEVERAGE = "beverage", "Beverage"

    name = models.CharField(max_length=200, unique=True, db_index=True)
    serving_size = models.CharField(
        max_length=100,
        default="100g",
        help_text="Serving size the nutrition values refer to, e.g. '100g', '1 cup', '1 medium'.",
    )
    calories = models.FloatField(
        default=0,
        help_text="Calories (kcal) per serving size.",
    )
    protein = models.FloatField(
        default=0,
        help_text="Protein (g) per serving size.",
    )
    carbs = models.FloatField(
        default=0,
        help_text="Carbohydrates (g) per serving size.",
    )
    fat = models.FloatField(
        default=0,
        help_text="Fat (g) per serving size.",
    )
    fiber = models.FloatField(
        default=0,
        help_text="Dietary fiber (g) per serving size.",
    )
    glycemic_index = models.IntegerField(
        null=True,
        blank=True,
        help_text="Glycemic index (optional).",
    )
    food_group = models.CharField(
        max_length=20,
        choices=FoodGroup.choices,
        default=FoodGroup.GRAINS,
    )
    is_veg = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """FoodItem model metadata."""

        db_table = "diet_food_items"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["food_group"]),
            models.Index(fields=["is_veg"]),
        ]

    def __str__(self) -> str:
        """Return a human-readable food item label."""
        return f"{self.name} ({self.serving_size})"


class DietPlan(TenantModelMixin):
    """A tenant-scoped diet plan made up of daily meal schedules."""

    class Goal(models.TextChoices):
        """Fitness goal the plan is designed for."""

        BULK = "bulk", "Bulk"
        CUT = "cut", "Cut"
        MAINTAIN = "maintain", "Maintain"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    goal = models.CharField(
        max_length=20,
        choices=Goal.choices,
        default=Goal.MAINTAIN,
    )
    daily_calories = models.PositiveIntegerField(default=0)
    protein_ratio = models.FloatField(
        default=30.0,
        help_text="Target protein share of calories (%).",
    )
    carb_ratio = models.FloatField(
        default=40.0,
        help_text="Target carb share of calories (%).",
    )
    fat_ratio = models.FloatField(
        default=30.0,
        help_text="Target fat share of calories (%).",
    )
    duration_days = models.PositiveIntegerField(default=7)
    is_template = models.BooleanField(
        default=False,
        help_text="Template plans can be duplicated to create new plans.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """DietPlan model metadata."""

        db_table = "diet_plans"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable diet plan label."""
        return f"{self.name} ({self.goal})"


class DietDay(TenantModelMixin):
    """A single day within a diet plan."""

    diet_plan = models.ForeignKey(
        DietPlan,
        on_delete=models.CASCADE,
        related_name="days",
    )
    day_number = models.PositiveIntegerField()
    total_calories = models.PositiveIntegerField(
        default=0,
        help_text="Auto-calculated sum of meal calories for the day.",
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        """DietDay model metadata."""

        db_table = "diet_days"
        ordering = ["diet_plan", "day_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["diet_plan", "day_number"],
                name="uq_diet_day_plan_number",
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable diet day label."""
        return f"{self.diet_plan.name} — Day {self.day_number}"

    def recalculate(self, *, save: bool = True) -> None:
        """Recompute ``total_calories`` from the day's meals.

        Args:
            save: Whether to persist the updated total to the database.
        """
        total = sum(
            (meal.calories for meal in self.meals.all()),
            start=0,
        )
        self.total_calories = round(total)
        if save:
            self.save(update_fields=["total_calories"])


class DietMeal(TenantModelMixin):
    """A meal entry within a diet day, referencing a food item and quantity."""

    class MealType(models.TextChoices):
        """Meal slots within a day."""

        BREAKFAST = "breakfast", "Breakfast"
        MORNING_SNACK = "morning_snack", "Morning Snack"
        LUNCH = "lunch", "Lunch"
        EVENING_SNACK = "evening_snack", "Evening Snack"
        DINNER = "dinner", "Dinner"

    diet_day = models.ForeignKey(
        DietDay,
        on_delete=models.CASCADE,
        related_name="meals",
    )
    meal_type = models.CharField(
        max_length=20,
        choices=MealType.choices,
        default=MealType.BREAKFAST,
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.PROTECT,
        related_name="diet_meals",
    )
    quantity = models.FloatField(
        default=1.0,
        help_text="Multiplier of the food item's serving size.",
    )
    calories = models.FloatField(
        default=0,
        help_text="Auto-calculated = food_item.calories × quantity.",
    )
    protein = models.FloatField(
        default=0,
        help_text="Auto-calculated = food_item.protein × quantity.",
    )
    carbs = models.FloatField(
        default=0,
        help_text="Auto-calculated = food_item.carbs × quantity.",
    )
    fat = models.FloatField(
        default=0,
        help_text="Auto-calculated = food_item.fat × quantity.",
    )

    class Meta:
        """DietMeal model metadata."""

        db_table = "diet_meals"
        ordering = ["diet_day", "meal_type", "id"]

    def __str__(self) -> str:
        """Return a human-readable diet meal label."""
        return f"{self.meal_type}: {self.food_item.name} × {self.quantity}"

    def recalculate(self, *, save: bool = True) -> None:
        """Recompute nutrition fields from the food item and quantity.

        Args:
            save: Whether to persist the updated values to the database.
        """
        food = self.food_item
        self.calories = round(food.calories * self.quantity, 2)
        self.protein = round(food.protein * self.quantity, 2)
        self.carbs = round(food.carbs * self.quantity, 2)
        self.fat = round(food.fat * self.quantity, 2)
        if save:
            self.save(
                update_fields=["calories", "protein", "carbs", "fat"],
            )

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the meal, auto-calculating nutrition and day totals.

        Args:
            *args: Positional arguments passed to ``Model.save``.
            **kwargs: Keyword arguments passed to ``Model.save``.
        """
        food = self.food_item
        self.calories = round(food.calories * self.quantity, 2)
        self.protein = round(food.protein * self.quantity, 2)
        self.carbs = round(food.carbs * self.quantity, 2)
        self.fat = round(food.fat * self.quantity, 2)
        super().save(*args, **kwargs)
        if self.diet_day_id is not None:
            # Refresh cached day total after the meal row is persisted.
            self.diet_day.recalculate()

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Delete the meal and refresh its day's calorie total.

        Args:
            *args: Positional arguments passed to ``Model.delete``.
            **kwargs: Keyword arguments passed to ``Model.delete``.

        Returns:
            The standard ``(row_count, details)`` tuple from ``Model.delete``.
        """
        day = self.diet_day
        result = super().delete(*args, **kwargs)
        day.recalculate()
        return result


class DietAssignment(TenantModelMixin):
    """Assignment of a diet plan to a customer for a date range."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="diet_assignments",
    )
    diet_plan = models.ForeignKey(
        DietPlan,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diet_assignments_made",
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """DietAssignment model metadata."""

        db_table = "diet_assignments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a human-readable assignment label."""
        return f"{self.customer.name} ← {self.diet_plan.name}"
