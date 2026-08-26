"""Tests for the AI nutrition app: models, services, serializers, APIs, permissions."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.ai_nutrition.models import (
    AIMealPlan,
    AIMealPlanItem,
    MacroLog,
    ShoppingList,
    ShoppingListItem,
)
from apps.ai_nutrition.services.nutrition_service import (
    MEAL_SLOTS,
    NutritionServiceError,
    generate_meal_plan,
    generate_shopping_list,
)
from apps.diet.models import FoodItem
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


def _make_food(**overrides) -> FoodItem:
    """Create a FoodItem with sensible defaults."""
    defaults = {
        "name": "White Rice",
        "serving_size": "100g",
        "calories": 130,
        "protein": 2.7,
        "carbs": 28.2,
        "fat": 0.3,
        "fiber": 0.4,
        "food_group": FoodItem.FoodGroup.GRAINS,
        "is_veg": True,
    }
    defaults.update(overrides)
    return FoodItem.objects.create(**defaults)


def _seed_catalog() -> None:
    """Seed a small food catalog covering each meal slot group."""
    specs = [
        ("Oats", FoodItem.FoodGroup.GRAINS, 150, 5.0, 27.0, 3.0, True),
        ("Paneer", FoodItem.FoodGroup.PROTEIN, 265, 18.0, 1.0, 21.0, True),
        ("Dal", FoodItem.FoodGroup.PROTEIN, 105, 7.0, 18.0, 1.0, True),
        ("Apple", FoodItem.FoodGroup.FRUIT, 52, 0.3, 14.0, 0.2, True),
        ("Yogurt", FoodItem.FoodGroup.DAIRY, 60, 3.5, 4.7, 3.3, True),
        ("Spinach", FoodItem.FoodGroup.VEGETABLE, 23, 2.9, 3.6, 0.4, True),
        ("Chicken", FoodItem.FoodGroup.PROTEIN, 165, 31.0, 0.0, 3.6, False),
        ("Almonds", FoodItem.FoodGroup.FAT, 579, 21.0, 22.0, 50.0, True),
    ]
    for name, group, cal, pro, carb, fat, veg in specs:
        FoodItem.objects.get_or_create(
            name=name,
            defaults={
                "serving_size": "100g",
                "calories": cal,
                "protein": pro,
                "carbs": carb,
                "fat": fat,
                "food_group": group,
                "is_veg": veg,
            },
        )


class MealPlanModelTests(TestCase):
    """Unit tests for the AIMealPlan model."""

    def setUp(self) -> None:
        """Create a tenant and user."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@ai.test")
        self.user = User.objects.create_user(
            email="user@ai.test",
            password="F1tNati0n!",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_meal_plan_requires_tenant(self) -> None:
        """Saving an AIMealPlan without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            AIMealPlan.objects.create(
                user=self.user,
                name="No Tenant Plan",
                target_calories=2000,
            )

    def test_meal_plan_default_status_active(self) -> None:
        """A new meal plan defaults to the active status."""
        plan = AIMealPlan.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Weekly Plan",
            target_calories=2000,
        )
        self.assertEqual(plan.status, AIMealPlan.Status.ACTIVE)
        self.assertEqual(str(plan), "Weekly Plan (user@ai.test)")

    def test_meal_plan_item_auto_calculates_nutrition(self) -> None:
        """Meal plan item macros are derived from the food item × servings."""
        food = _make_food(calories=130, protein=2.7, carbs=28.2, fat=0.3)
        plan = AIMealPlan.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Plan",
        )
        item = AIMealPlanItem.objects.create(
            tenant=self.tenant,
            meal_plan=plan,
            day_of_week=0,
            meal_type=AIMealPlanItem.MealType.BREAKFAST,
            food_item=food,
            servings=2.0,
        )
        self.assertEqual(item.calories, 260.0)
        self.assertEqual(item.protein_g, 5.4)
        self.assertEqual(item.carbs_g, 56.4)
        self.assertEqual(item.fat_g, 0.6)


class ShoppingListModelTests(TestCase):
    """Unit tests for ShoppingList / ShoppingListItem."""

    def setUp(self) -> None:
        """Create tenant and user."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@ai.test")
        self.user = User.objects.create_user(
            email="u@ai.test", password="x", role=User.Role.CUSTOMER, tenant=self.tenant
        )
        self.plan = AIMealPlan.objects.create(
            tenant=self.tenant, user=self.user, name="P", target_calories=2000
        )

    def test_shopping_list_status_defaults_active(self) -> None:
        """New shopping list defaults to active."""
        sl = ShoppingList.objects.create(
            tenant=self.tenant,
            user=self.user,
            meal_plan=self.plan,
            name="Groceries",
        )
        self.assertEqual(sl.status, ShoppingList.Status.ACTIVE)

    def test_item_requires_tenant(self) -> None:
        """ShoppingListItem without tenant raises."""
        sl = ShoppingList.objects.create(
            tenant=self.tenant, user=self.user, meal_plan=self.plan, name="Groceries"
        )
        food = _make_food()
        with self.assertRaises(ValueError):
            ShoppingListItem.objects.create(
                shopping_list=sl, food_item=food, quantity=1.0, unit="serving"
            )


class MacroLogModelTests(TestCase):
    """Unit tests for the MacroLog model."""

    def setUp(self) -> None:
        """Create tenant and user."""
        self.tenant = provision_tenant(name="Gym", contact_email="g@ai.test")
        self.user = User.objects.create_user(
            email="u@ai.test", password="x", role=User.Role.CUSTOMER, tenant=self.tenant
        )

    def test_unique_per_tenant_user_date(self) -> None:
        """Only one macro log per user per day within a tenant."""
        MacroLog.objects.create(
            tenant=self.tenant, user=self.user, date=date(2026, 1, 1), calories_consumed=100
        )
        with self.assertRaises(Exception):
            MacroLog.objects.create(
                tenant=self.tenant, user=self.user, date=date(2026, 1, 1)
            )

    def test_macro_log_str(self) -> None:
        """String representation shows user and date."""
        log = MacroLog.objects.create(
            tenant=self.tenant, user=self.user, date=date(2026, 1, 1)
        )
        self.assertEqual(str(log), "u@ai.test — 2026-01-01")


class NutritionServiceTests(TestCase):
    """Unit tests for the mock AI nutrition generator."""

    def setUp(self) -> None:
        """Create a tenant and seed a catalog."""
        self.tenant = provision_tenant(name="Gym", contact_email="svc@ai.test")
        self.user = User.objects.create_user(
            email="svc@ai.test", password="x", role=User.Role.CUSTOMER, tenant=self.tenant
        )
        _seed_catalog()

    def test_generates_28_items_for_7_days(self) -> None:
        """A 7-day plan has 4 meals per day = 28 items."""
        result = generate_meal_plan(
            tenant=self.tenant,
            user=self.user,
            name="Week",
            target_calories=2000,
            target_protein_g=120,
            target_carbs_g=250,
            target_fat_g=50,
            seed=42,
        )
        self.assertEqual(len(result["items"]), 7 * len(MEAL_SLOTS))
        self.assertEqual(result["plan"]["target_calories"], 2000)

    def test_days_respected(self) -> None:
        """A 3-day plan yields 12 items."""
        result = generate_meal_plan(
            tenant=self.tenant,
            user=self.user,
            name="Mini",
            target_calories=1500,
            target_protein_g=30,
            target_carbs_g=0,
            target_fat_g=0,
            days=3,
            seed=1,
        )
        self.assertEqual(len(result["items"]), 12)

    def test_vegetarian_restriction_only_veg(self) -> None:
        """With vegetarian restriction, non-veg items are never chosen."""
        result = generate_meal_plan(
            tenant=self.tenant,
            user=self.user,
            name="Veg",
            target_calories=2000,
            target_protein_g=40,
            target_carbs_g=0,
            target_fat_g=0,
            dietary_restrictions=["vegetarian"],
            days=1,
            seed=7,
        )
        item_ids = {i["food_item_id"] for i in result["items"]}
        self.assertTrue(all(FoodItem.objects.get(id=i).is_veg for i in item_ids))

    def test_deterministic_with_seed(self) -> None:
        """Same seed yields the same plan."""
        a = generate_meal_plan(
            tenant=self.tenant, user=self.user, name="A", target_calories=1,
            target_protein_g=0, target_carbs_g=0, target_fat_g=0, days=1, seed=99,
        )
        b = generate_meal_plan(
            tenant=self.tenant, user=self.user, name="B", target_calories=1,
            target_protein_g=0, target_carbs_g=0, target_fat_g=0, days=1, seed=99,
        )
        self.assertEqual(
            [i["food_item_id"] for i in a["items"]],
            [i["food_item_id"] for i in b["items"]],
        )

    def test_raises_when_no_food(self) -> None:
        """Service raises a clear error when the catalog is empty."""
        FoodItem.objects.all().delete()
        with self.assertRaises(NutritionServiceError):
            generate_meal_plan(
                tenant=self.tenant,
                user=self.user,
                name="Empty",
                target_calories=2000,
                target_protein_g=0,
                target_carbs_g=0,
                target_fat_g=0,
                days=1,
                seed=1,
            )

    def test_generate_shopping_list_aggregates(self) -> None:
        """Shopping list aggregation combines servings for the same food."""
        result = generate_meal_plan(
            tenant=self.tenant,
            user=self.user,
            name="Week",
            target_calories=2000,
            target_protein_g=0,
            target_carbs_g=0,
            target_fat_g=0,
            days=1,
            seed=5,
        )
        plan = AIMealPlan.objects.create(
            tenant=self.tenant, user=self.user, name="Week", target_calories=2000
        )
        items = [
            AIMealPlanItem.objects.create(
                tenant=self.tenant, meal_plan=plan, **i
            )
            for i in result["items"]
        ]
        shopping = generate_shopping_list(meal_plan_items=items, name="Shop")
        self.assertTrue(shopping)
        self.assertIn("food_item_id", shopping[0])
        self.assertEqual(shopping[0]["unit"], "serving")


class AINutritionAPIBase(APITestCase):
    """Shared base for AI nutrition API tests."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, and seed food."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@ai.api")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@ai.api",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        _seed_catalog()

        self.customer_user = User.objects.create_user(
            email="cust@ai.api",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="omer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

        self.plan = AIMealPlan.objects.create(
            tenant=self.tenant,
            user=self.customer_user,
            name="Weekly Plan",
            target_calories=2000,
            target_protein_g=40,
        )
        self.item = AIMealPlanItem.objects.create(
            tenant=self.tenant,
            meal_plan=self.plan,
            day_of_week=0,
            meal_type=AIMealPlanItem.MealType.BREAKFAST,
            food_item=FoodItem.objects.get(name="Oats"),
            servings=1.0,
        )
        self.shopping_list = ShoppingList.objects.create(
            tenant=self.tenant,
            user=self.customer_user,
            meal_plan=self.plan,
            name="Groceries",
        )
        self.shopping_item = ShoppingListItem.objects.create(
            tenant=self.tenant,
            shopping_list=self.shopping_list,
            food_item=FoodItem.objects.get(name="Oats"),
            quantity=1.0,
            unit="serving",
        )


class MealPlanAPITests(AINutritionAPIBase):
    """Tests for the meal plan endpoints."""

    def test_list_meal_plans(self) -> None:
        """Authenticated users can list tenant meal plans."""
        response = self.client.get("/api/v1/ai/nutrition/meal-plan/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_generates_meal_plan(self) -> None:
        """POST creates a plan with generated items."""
        payload = {
            "name": "Generated Week",
            "target_calories": 2000,
            "target_protein_g": 40,
            "target_carbs_g": 250,
            "target_fat_g": 50,
            "cuisine_preference": "indian",
            "dietary_restrictions": ["vegetarian"],
        }
        response = self.client.post(
            "/api/v1/ai/nutrition/meal-plan/", payload, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["items"]), 28)
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(response.data["user_email"], "owner@ai.api")

    def test_generate_requires_food_catalog(self) -> None:
        """POST fails gracefully when no food items exist."""
        # Remove dependent rows first (PROTECT FK) so the catalog can be emptied.
        ShoppingListItem.objects.all().delete()
        AIMealPlanItem.objects.all().delete()
        FoodItem.objects.all().delete()
        response = self.client.post(
            "/api/v1/ai/nutrition/meal-plan/",
            {"name": "Empty", "target_calories": 2000},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_detail_includes_items(self) -> None:
        """GET detail returns nested items."""
        response = self.client.get(f"/api/v1/ai/nutrition/meal-plan/{self.plan.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["food_item"]["name"], "Oats")

    def test_patch_updates_status(self) -> None:
        """PATCH updates plan fields."""
        response = self.client.patch(
            f"/api/v1/ai/nutrition/meal-plan/{self.plan.id}/",
            {"status": "archived"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "archived")

    def test_delete_removes_plan(self) -> None:
        """DELETE removes the plan."""
        response = self.client.delete(f"/api/v1/ai/nutrition/meal-plan/{self.plan.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(AIMealPlan.objects.filter(id=self.plan.id).exists())

    def test_tenant_isolation(self) -> None:
        """A different tenant cannot access the plan."""
        other = provision_tenant(name="Other", contact_email="other@ai.api")
        other_owner = create_owner_user(
            tenant=other, email="other@ai.api", password_hash="x", contact_name="Other"
        )
        token = issue_token(other_owner, other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/ai/nutrition/meal-plan/{self.plan.id}/")
        self.assertEqual(response.status_code, 404)


class ShoppingListAPITests(AINutritionAPIBase):
    """Tests for the shopping list endpoints."""

    def test_list_shopping_lists(self) -> None:
        """Authenticated users can list tenant shopping lists."""
        response = self.client.get("/api/v1/ai/nutrition/shopping-list/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_generate_from_meal_plan(self) -> None:
        """POST generates a shopping list from a meal plan."""
        response = self.client.post(
            "/api/v1/ai/nutrition/shopping-list/",
            {"meal_plan": self.plan.id, "name": "Week Shop"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["name"], "Week Shop")
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["food_item"]["name"], "Oats")

    def test_generate_requires_meal_plan(self) -> None:
        """POST without meal_plan returns 400."""
        response = self.client.post(
            "/api/v1/ai/nutrition/shopping-list/", {}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_marks_items_purchased(self) -> None:
        """PATCH with purchased_items marks items as purchased."""
        response = self.client.patch(
            f"/api/v1/ai/nutrition/shopping-list/{self.shopping_list.id}/",
            {"purchased_items": [self.shopping_item.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.shopping_item.refresh_from_db()
        self.assertTrue(self.shopping_item.is_purchased)

    def test_patch_updates_status(self) -> None:
        """PATCH updates shopping list status."""
        response = self.client.patch(
            f"/api/v1/ai/nutrition/shopping-list/{self.shopping_list.id}/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")

    def test_delete_shopping_list(self) -> None:
        """DELETE removes the shopping list."""
        response = self.client.delete(
            f"/api/v1/ai/nutrition/shopping-list/{self.shopping_list.id}/"
        )
        self.assertEqual(response.status_code, 204)


class MacroLogAPITests(AINutritionAPIBase):
    """Tests for the macro tracking endpoints."""

    def test_create_log(self) -> None:
        """POST /track/ logs daily intake."""
        payload = {
            "date": "2026-08-24",
            "calories_consumed": 1800,
            "protein_consumed_g": 90,
            "carbs_consumed_g": 200,
            "fat_consumed_g": 60,
            "water_intake_ml": 2500,
        }
        response = self.client.post("/api/v1/ai/nutrition/track/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["user"], self.owner.id)
        self.assertEqual(MacroLog.objects.count(), 1)

    def test_list_logs(self) -> None:
        """GET /track/ lists logs."""
        MacroLog.objects.create(
            tenant=self.tenant,
            user=self.owner,
            date=date(2026, 8, 24),
            calories_consumed=1800,
        )
        response = self.client.get("/api/v1/ai/nutrition/track/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_trend_weekly(self) -> None:
        """GET /track/trend/ returns weekly aggregates."""
        MacroLog.objects.create(
            tenant=self.tenant, user=self.owner, date=date(2026, 8, 24), calories_consumed=1800
        )
        MacroLog.objects.create(
            tenant=self.tenant, user=self.owner, date=date(2026, 8, 25), calories_consumed=2000
        )
        response = self.client.get("/api/v1/ai/nutrition/track/trend/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["period"], "weekly")
        self.assertEqual(len(response.data["buckets"]), 2)
        self.assertEqual(response.data["averages"]["calories_consumed"], 1900.0)

    def test_trend_empty(self) -> None:
        """Trend with no logs returns empty averages."""
        response = self.client.get("/api/v1/ai/nutrition/track/trend/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["averages"]["calories_consumed"], 0)
        self.assertEqual(response.data["buckets"], [])


class PermissionAPITests(AINutritionAPIBase):
    """Tests for role/permission enforcement."""

    def test_unauthenticated_denied(self) -> None:
        """No token => 401."""
        self.client.credentials()
        response = self.client.get("/api/v1/ai/nutrition/meal-plan/")
        self.assertEqual(response.status_code, 401)

    def test_customer_can_view_own_plan(self) -> None:
        """A customer can access their own meal plan."""
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/ai/nutrition/meal-plan/{self.plan.id}/")
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_create_meal_plan(self) -> None:
        """A customer lacks the create permission."""
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            "/api/v1/ai/nutrition/meal-plan/",
            {"name": "Nope", "target_calories": 2000},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
