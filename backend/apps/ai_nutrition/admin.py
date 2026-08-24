"""AI Nutrition admin registrations."""

from django.contrib import admin

from apps.ai_nutrition.models import (
    AIMealPlan,
    AIMealPlanItem,
    MacroLog,
    ShoppingList,
    ShoppingListItem,
)


class AIMealPlanItemInline(admin.TabularInline):
    """Inline editor for meal plan items."""

    model = AIMealPlanItem
    extra = 0


class ShoppingListItemInline(admin.TabularInline):
    """Inline editor for shopping list items."""

    model = ShoppingListItem
    extra = 0


@admin.register(AIMealPlan)
class AIMealPlanAdmin(admin.ModelAdmin):
    """Admin for AI meal plans."""

    list_display = ("name", "user", "tenant", "target_calories", "status", "created_at")
    list_filter = ("status", "cuisine_preference")
    search_fields = ("name", "user__email")
    inlines = [AIMealPlanItemInline]


@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    """Admin for shopping lists."""

    list_display = ("name", "user", "tenant", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "user__email")
    inlines = [ShoppingListItemInline]


@admin.register(MacroLog)
class MacroLogAdmin(admin.ModelAdmin):
    """Admin for macro logs."""

    list_display = (
        "user",
        "tenant",
        "date",
        "calories_consumed",
        "protein_consumed_g",
        "water_intake_ml",
    )
    list_filter = ("date",)
    search_fields = ("user__email",)
