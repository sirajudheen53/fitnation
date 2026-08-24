"""Tests for the diet app: models, serializers, APIs, permissions, and isolation."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.diet.models import (
    DietAssignment,
    DietDay,
    DietMeal,
    DietPlan,
    FoodItem,
)
from apps.diet.serializers import (
    DietMealSerializer,
    DietPlanSerializer,
    FoodItemSerializer,
)
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


def _make_food(**overrides: object) -> FoodItem:
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


class FoodItemModelTests(TestCase):
    """Unit tests for the global FoodItem model."""

    def test_food_item_requires_no_tenant(self) -> None:
        """FoodItem is global and can be created without a tenant."""
        food = FoodItem.objects.create(
            name="Test Dal",
            serving_size="100g",
            calories=105,
            protein=7.0,
            carbs=18.0,
            fat=1.0,
            fiber=7.0,
            food_group=FoodItem.FoodGroup.PROTEIN,
            is_veg=True,
        )
        self.assertEqual(food.name, "Test Dal")
        self.assertEqual(str(food), "Test Dal (100g)")

    def test_food_item_name_unique(self) -> None:
        """Food item names are globally unique."""
        _make_food()
        with self.assertRaises(Exception):
            _make_food()


class DietPlanModelTests(TestCase):
    """Unit tests for the DietPlan model."""

    def setUp(self) -> None:
        """Create a tenant for plan tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_diet_plan_requires_tenant(self) -> None:
        """Saving a DietPlan without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            DietPlan.objects.create(name="No Tenant Plan")

    def test_diet_plan_str(self) -> None:
        """The plan string includes name and goal."""
        plan = DietPlan.objects.create(
            tenant=self.tenant,
            name="Bulk Plan",
            goal=DietPlan.Goal.BULK,
        )
        self.assertEqual(str(plan), "Bulk Plan (bulk)")


class DietMealAutoCalcTests(TestCase):
    """Unit tests for auto-calculation of meal nutrition and day totals."""

    def setUp(self) -> None:
        """Create a tenant, plan, day, and food item."""
        self.tenant = provision_tenant("Iron Peak", contact_email="own2@local.test")
        self.plan = DietPlan.objects.create(
            tenant=self.tenant,
            name="Cut Plan",
            goal=DietPlan.Goal.CUT,
        )
        self.day = DietDay.objects.create(
            tenant=self.tenant,
            diet_plan=self.plan,
            day_number=1,
        )
        self.food = _make_food(calories=130, protein=2.7, carbs=28.2, fat=0.3)

    def test_meal_nutrition_auto_calculated(self) -> None:
        """Meal calories/protein/carbs/fat are food item × quantity."""
        meal = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            meal_type=DietMeal.MealType.BREAKFAST,
            food_item=self.food,
            quantity=2.0,
        )
        self.assertEqual(meal.calories, round(130 * 2.0, 2))
        self.assertEqual(meal.protein, round(2.7 * 2.0, 2))
        self.assertEqual(meal.carbs, round(28.2 * 2.0, 2))
        self.assertEqual(meal.fat, round(0.3 * 2.0, 2))

    def test_day_total_auto_calculated(self) -> None:
        """DietDay.total_calories sums meal calories."""
        DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=1.0,
        )
        DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=2.0,
        )
        self.day.refresh_from_db()
        self.assertEqual(self.day.total_calories, round(130 * 1.0 + 130 * 2.0))

    def test_meal_delete_recalculates_day(self) -> None:
        """Deleting a meal updates the day's calorie total."""
        meal = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=3.0,
        )
        self.day.refresh_from_db()
        self.assertEqual(self.day.total_calories, 390)
        meal.delete()
        self.day.refresh_from_db()
        self.assertEqual(self.day.total_calories, 0)

    def test_recalculate_updates_meal(self) -> None:
        """Recalculate recomputes nutrition from food × quantity."""
        meal = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=1.0,
        )
        meal.quantity = 3.0
        meal.recalculate()
        self.assertEqual(meal.calories, round(130 * 3.0, 2))


class DietAssignmentModelTests(TestCase):
    """Unit tests for DietAssignment model."""

    def setUp(self) -> None:
        """Create tenant, plan, and customer."""
        self.tenant = provision_tenant("Iron Peak", contact_email="own@local.test")
        self.plan = DietPlan.objects.create(
            tenant=self.tenant,
            name="Cut Plan",
            goal=DietPlan.Goal.CUT,
        )
        self.user = User.objects.create_user(
            email="cust@local.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="omer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Customer",
            email="cust@local.test",
        )

    def test_assignment_defaults_active(self) -> None:
        """Assignments default to active and today's start date."""
        assignment = DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
        )
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.start_date, date.today())
        self.assertIsNone(assignment.assigned_by)


class DietSerializerTests(TestCase):
    """Unit tests for diet serializers."""

    def setUp(self) -> None:
        """Create tenant, plan, food, and day with a meal."""
        self.tenant = provision_tenant("Iron Peak", contact_email="ser@local.test")
        self.food = _make_food()
        self.plan = DietPlan.objects.create(
            tenant=self.tenant,
            name="Plan",
            goal=DietPlan.Goal.MAINTAIN,
        )
        self.day = DietDay.objects.create(
            tenant=self.tenant,
            diet_plan=self.plan,
            day_number=1,
        )
        self.meal = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=2.0,
        )

    def test_food_item_serializer_fields(self) -> None:
        """FoodItemSerializer exposes expected fields."""
        serializer = FoodItemSerializer(self.food)
        data = serializer.data
        self.assertIn("name", data)
        self.assertIn("food_group", data)
        self.assertIn("is_veg", data)
        self.assertEqual(data["calories"], 130)

    def test_meal_serializer_nutrition_read_only(self) -> None:
        """Meal nutrition fields are read-only in the serializer."""
        serializer = DietMealSerializer(self.meal)
        self.assertEqual(serializer.data["calories"], round(130 * 2.0, 2))
        meta = serializer.Meta.read_only_fields
        self.assertIn("calories", meta)
        self.assertIn("protein", meta)
        self.assertIn("carbs", meta)
        self.assertIn("fat", meta)

    def test_plan_serializer_nests_days(self) -> None:
        """DietPlanSerializer nests days with meals."""
        serializer = DietPlanSerializer(self.plan, context={"request": None})
        self.assertEqual(len(serializer.data["days"]), 1)
        self.assertEqual(serializer.data["days"][0]["total_calories"], round(130 * 2.0))

    def test_meal_serializer_rejects_non_positive_quantity(self) -> None:
        """Quantity validation rejects zero or negative values."""
        serializer = DietMealSerializer(data={"quantity": 0})
        serializer.is_valid()
        self.assertIn("quantity", serializer.errors)


class DietAPIBase(APITestCase):
    """Shared base for diet API tests."""

    def setUp(self) -> None:
        """Create a tenant, owner, customer, food, and plan."""
        self.tenant = provision_tenant("Iron Peak", contact_email="owner@diet.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@diet.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.food = _make_food()
        self.plan = DietPlan.objects.create(
            tenant=self.tenant,
            name="Bulk Plan",
            goal=DietPlan.Goal.BULK,
            daily_calories=2500,
            protein_ratio=30.0,
            carb_ratio=40.0,
            fat_ratio=30.0,
        )
        self.day = DietDay.objects.create(
            tenant=self.tenant,
            diet_plan=self.plan,
            day_number=1,
        )
        self.meal = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=1.0,
        )

        self.customer_user = User.objects.create_user(
            email="cust@diet.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="omer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.customer_user,
            name="Customer One",
            email="cust@diet.test",
        )


class FoodItemAPITests(DietAPIBase):
    """Tests for the global food item endpoints."""

    def test_list_food_items(self) -> None:
        """Authenticated users can list food items."""
        response = self.client.get("/api/v1/food-items/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_search_food_items_by_name(self) -> None:
        """Food items can be searched by name."""
        _make_food(name="Paneer Tikka")
        response = self.client.get("/api/v1/food-items/?search=paneer")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Paneer Tikka")

    def test_filter_food_items_by_group(self) -> None:
        """Food items can be filtered by food_group."""
        _make_food(name="Almonds", food_group=FoodItem.FoodGroup.FAT)
        response = self.client.get(
            "/api/v1/food-items/?food_group=fat",
        )
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Almonds", names)

    def test_filter_food_items_by_is_veg(self) -> None:
        """Food items can be filtered by vegetarian flag."""
        _make_food(name="Chicken", is_veg=False)
        response = self.client.get("/api/v1/food-items/?is_veg=false")
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Chicken", names)

    def test_create_food_item_requires_staff(self) -> None:
        """Owner can create a food item."""
        response = self.client.post(
            "/api/v1/food-items/",
            {
                "name": "Almond Butter",
                "serving_size": "1 tbsp",
                "calories": 98,
                "protein": 3.4,
                "carbs": 3.0,
                "fat": 9.0,
                "fiber": 1.6,
                "food_group": "fat",
                "is_veg": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Almond Butter")

    def test_update_food_item(self) -> None:
        """Food items can be updated."""
        response = self.client.patch(
            f"/api/v1/food-items/{self.food.id}/",
            {"calories": 140},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.food.refresh_from_db()
        self.assertEqual(self.food.calories, 140)

    def test_unauthenticated_list_denied(self) -> None:
        """Unauthenticated requests cannot list food items."""
        self.client.credentials()
        response = self.client.get("/api/v1/food-items/")
        self.assertEqual(response.status_code, 401)


class DietPlanAPITests(DietAPIBase):
    """Tests for the diet plan endpoints."""

    def test_list_diet_plans(self) -> None:
        """Owners can list diet plans in their tenant."""
        response = self.client.get("/api/v1/diet-plans/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_diet_plans_by_goal(self) -> None:
        """Diet plans can be filtered by goal."""
        DietPlan.objects.create(
            tenant=self.tenant,
            name="Cut Plan",
            goal=DietPlan.Goal.CUT,
        )
        response = self.client.get("/api/v1/diet-plans/?goal=cut")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["goal"], "cut")

    def test_create_diet_plan_with_nested_days_and_meals(self) -> None:
        """A diet plan can be created with days and meals in one request."""
        payload = {
            "name": "New Cut Plan",
            "goal": "cut",
            "daily_calories": 1800,
            "protein_ratio": 30,
            "carb_ratio": 40,
            "fat_ratio": 30,
            "duration_days": 7,
            "days": [
                {
                    "day_number": 1,
                    "notes": "Leg day",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "food_item": self.food.id,
                            "quantity": 1.5,
                        },
                    ],
                },
                {
                    "day_number": 2,
                    "meals": [
                        {
                            "meal_type": "lunch",
                            "food_item": self.food.id,
                            "quantity": 2.0,
                        },
                    ],
                },
            ],
        }
        response = self.client.post(
            "/api/v1/diet-plans/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["days"]), 2)
        self.assertEqual(response.data["days"][0]["meals"][0]["quantity"], 1.5)

        plan = DietPlan.objects.get(name="New Cut Plan")
        self.assertEqual(plan.days.count(), 2)
        self.assertEqual(plan.days.get(day_number=1).meals.count(), 1)
        # total calories auto-calculated
        self.assertEqual(plan.days.get(day_number=1).total_calories, round(130 * 1.5))

    def test_update_diet_plan(self) -> None:
        """Diet plans can be updated."""
        response = self.client.patch(
            f"/api/v1/diet-plans/{self.plan.id}/",
            {"name": "Renamed Plan"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.name, "Renamed Plan")

    def test_duplicate_diet_plan_as_template(self) -> None:
        """A plan can be duplicated as a template with copied days/meals."""
        response = self.client.post(f"/api/v1/diet-plans/{self.plan.id}/duplicate/")
        self.assertEqual(response.status_code, 201)
        copied = DietPlan.objects.get(name="Bulk Plan (copy)")
        self.assertTrue(copied.is_template)
        self.assertEqual(copied.days.count(), 1)
        self.assertEqual(copied.days.first().meals.count(), 1)

    def test_nutrition_breakdown(self) -> None:
        """The nutrition breakdown endpoint returns macro totals."""
        response = self.client.get(
            f"/api/v1/diet-plans/{self.plan.id}/nutrition-breakdown/",
        )
        self.assertEqual(response.status_code, 200)
        data = response.data
        # One meal: food 130 cal, 2.7 protein, 28.2 carbs, 0.3 fat
        self.assertEqual(data["total_calories"], 130.0)
        self.assertEqual(data["total_protein"], 2.7)
        self.assertEqual(data["total_carbs"], 28.2)
        self.assertEqual(data["total_fat"], 0.3)
        self.assertEqual(data["protein_grams_per_day"], 2.7)

    def test_plan_tenant_isolation(self) -> None:
        """Plans are scoped to their tenant."""
        other = provision_tenant("Other Gym", contact_email="o@other.test")
        DietPlan.objects.create(tenant=other, name="Other Plan")
        response = self.client.get("/api/v1/diet-plans/")
        self.assertEqual(response.status_code, 200)
        names = [p["name"] for p in response.data["results"]]
        self.assertNotIn("Other Plan", names)


class DietDayMealAPITests(DietAPIBase):
    """Tests for the diet-day and diet-meal endpoints."""

    def test_create_diet_day(self) -> None:
        """Owners can create a diet day nested under a plan."""
        response = self.client.post(
            "/api/v1/diet-days/",
            {
                "diet_plan": self.plan.id,
                "day_number": 3,
                "notes": "Rest day",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["day_number"], 3)

    def test_list_diet_days_filter_by_plan(self) -> None:
        """Diet days can be listed filtered by plan."""
        response = self.client.get(
            f"/api/v1/diet-days/?diet_plan={self.plan.id}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_diet_meal(self) -> None:
        """Owners can create a diet meal with auto nutrition."""
        response = self.client.post(
            "/api/v1/diet-meals/",
            {
                "diet_day": self.day.id,
                "meal_type": "dinner",
                "food_item": self.food.id,
                "quantity": 3.0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["calories"], round(130 * 3.0, 2))

    def test_update_diet_meal_recalculates(self) -> None:
        """Updating meal quantity recalculates nutrition and day total."""
        meal = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=1.0,
        )
        response = self.client.patch(
            f"/api/v1/diet-meals/{meal.id}/",
            {"quantity": 4.0},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        meal.refresh_from_db()
        self.assertEqual(meal.calories, round(130 * 4.0, 2))
        self.day.refresh_from_db()
        self.assertEqual(
            self.day.total_calories,
            round(130 * 1.0 + 130 * 4.0),
        )

    def test_meal_create_requires_valid_day(self) -> None:
        """Creating a meal with an invalid diet_day returns 404."""
        response = self.client.post(
            "/api/v1/diet-meals/",
            {
                "diet_day": 99999,
                "food_item": self.food.id,
                "quantity": 1.0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class DietAssignmentAPITests(DietAPIBase):
    """Tests for diet assignment endpoints."""

    def _create_assignment(self) -> DietAssignment:
        """Create a diet assignment."""
        return DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
            assigned_by=self.owner,
            start_date=date.today(),
        )

    def test_assign_diet_to_customer(self) -> None:
        """Owners can assign a diet plan to a customer."""
        response = self.client.post(
            "/api/v1/diet-assignments/",
            {
                "customer": self.customer.id,
                "diet_plan": self.plan.id,
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=30)),
                "is_active": True,
                "notes": "Follow closely",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["customer_name"], "Customer One")
        self.assertEqual(response.data["assigned_by"], self.owner.id)

    def test_list_assignments_filter_by_customer(self) -> None:
        """Assignments can be listed filtered by customer."""
        self._create_assignment()
        response = self.client.get(
            f"/api/v1/diet-assignments/?customer={self.customer.id}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_active_assignments_action(self) -> None:
        """The active action returns the customer's active assignment."""
        self._create_assignment()
        response = self.client.get(
            f"/api/v1/diet-assignments/active/?customer={self.customer.id}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertTrue(response.data[0]["is_active"])

    def test_active_requires_customer_param(self) -> None:
        """The active action requires a customer param for non-customers."""
        response = self.client.get("/api/v1/diet-assignments/active/")
        self.assertEqual(response.status_code, 400)


class DietPermissionsTests(DietAPIBase):
    """Tests for role-based permissions on diet endpoints."""

    def _login(self, user: User) -> None:
        """Authenticate the API client as the given user."""
        token = issue_token(user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_customer_can_view_assigned_plan(self) -> None:
        """A customer can view their assigned diet plan."""
        DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
            assigned_by=self.owner,
        )
        self._login(self.customer_user)
        response = self.client.get(f"/api/v1/diet-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Bulk Plan")

    def test_customer_cannot_create_diet_plan(self) -> None:
        """A customer cannot create a diet plan."""
        self._login(self.customer_user)
        response = self.client.post(
            "/api/v1/diet-plans/",
            {"name": "Not Allowed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_edit_food_item(self) -> None:
        """A customer cannot modify food items."""
        self._login(self.customer_user)
        response = self.client.post(
            "/api/v1/food-items/",
            {"name": "Hack"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_other_tenant_cannot_access(self) -> None:
        """A user from another tenant cannot access this tenant's plan."""
        other = provision_tenant(name="Other Gym", contact_email="other@perm.test")
        other_owner = create_owner_user(
            tenant=other,
            email="other@perm.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        token = issue_token(other_owner, other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/diet-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 404)

    def test_dietitian_can_create_food_item(self) -> None:
        """A dietitian user can create a food item."""
        dietitian = User.objects.create_user(
            email="diet@perm.test",
            password="F1tNati0n!",
            first_name="Diet",
            last_name="itian",
            role=User.Role.DIETITIAN,
            tenant=self.tenant,
        )
        self._login(dietitian)
        response = self.client.post(
            "/api/v1/food-items/",
            {
                "name": "Dhaula Dal",
                "serving_size": "100g",
                "calories": 100,
                "protein": 8,
                "carbs": 18,
                "fat": 1,
                "fiber": 5,
                "food_group": "protein",
                "is_veg": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)


class DietExtendedAPITests(DietAPIBase):
    """Additional coverage for update/delete and nested write flows."""

    def test_update_diet_day(self) -> None:
        """A diet day can be updated via the day endpoint."""
        response = self.client.patch(
            f"/api/v1/diet-days/{self.day.id}/",
            {"notes": "Updated notes"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.day.refresh_from_db()
        self.assertEqual(self.day.notes, "Updated notes")

    def test_update_diet_day_with_nested_meals(self) -> None:
        """Updating a day with meals replaces its meals and recalculates."""
        other_food = _make_food(name="Brown Rice", calories=200)
        response = self.client.put(
            f"/api/v1/diet-days/{self.day.id}/",
            {
                "diet_plan": self.plan.id,
                "day_number": 1,
                "meals": [
                    {
                        "meal_type": "dinner",
                        "food_item": other_food.id,
                        "quantity": 2.0,
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.day.refresh_from_db()
        self.assertEqual(self.day.meals.count(), 1)
        self.assertEqual(self.day.total_calories, round(200 * 2.0))

    def test_delete_diet_day(self) -> None:
        """A diet day can be deleted."""
        response = self.client.delete(f"/api/v1/diet-days/{self.day.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(DietDay.objects.filter(id=self.day.id).exists())

    def test_delete_diet_meal(self) -> None:
        """A diet meal can be deleted and the day total updates."""
        extra = DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=self.food,
            quantity=2.0,
        )
        response = self.client.delete(f"/api/v1/diet-meals/{extra.id}/")
        self.assertEqual(response.status_code, 204)
        self.day.refresh_from_db()
        self.assertEqual(self.day.total_calories, round(130 * 1.0))

    def test_update_diet_assignment(self) -> None:
        """A diet assignment can be updated."""
        assignment = DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
            assigned_by=self.owner,
        )
        response = self.client.patch(
            f"/api/v1/diet-assignments/{assignment.id}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_delete_diet_assignment(self) -> None:
        """A diet assignment can be deleted."""
        assignment = DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
            assigned_by=self.owner,
        )
        response = self.client.delete(
            f"/api/v1/diet-assignments/{assignment.id}/",
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(DietAssignment.objects.filter(id=assignment.id).exists())

    def test_delete_diet_plan(self) -> None:
        """A diet plan can be deleted."""
        response = self.client.delete(f"/api/v1/diet-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(DietPlan.objects.filter(id=self.plan.id).exists())

    def test_delete_food_item(self) -> None:
        """A food item can be deleted by an owner."""
        item = _make_food(name="Solo Food")
        response = self.client.delete(f"/api/v1/food-items/{item.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(FoodItem.objects.filter(id=item.id).exists())

    def test_nutrition_breakdown_multiple_meals(self) -> None:
        """Nutrition breakdown aggregates across multiple meals."""
        second = _make_food(name="Chicken", calories=165, protein=31.0, carbs=0.0, fat=3.6)
        DietMeal.objects.create(
            tenant=self.tenant,
            diet_day=self.day,
            food_item=second,
            quantity=1.0,
        )
        response = self.client.get(
            f"/api/v1/diet-plans/{self.plan.id}/nutrition-breakdown/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_calories"], 130 + 165)
        self.assertEqual(response.data["total_protein"], 2.7 + 31.0)

    def test_customer_active_assignment_self(self) -> None:
        """A customer can query their own active assignment without a param."""
        DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
            assigned_by=self.owner,
            is_active=True,
        )
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/v1/diet-assignments/active/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_customer_cannot_update_assignment(self) -> None:
        """A customer cannot update a diet assignment."""
        assignment = DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            diet_plan=self.plan,
            assigned_by=self.owner,
        )
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.patch(
            f"/api/v1/diet-assignments/{assignment.id}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class SeedFoodItemsCommandTests(TestCase):
    """Tests for the seed_food_items management command."""

    def test_seed_creates_100_plus_items(self) -> None:
        """Running the seed command creates 100+ food items."""
        from django.core.management import call_command

        call_command("seed_food_items")
        self.assertGreaterEqual(FoodItem.objects.count(), 100)

    def test_seed_is_idempotent(self) -> None:
        """Running the seed command twice does not duplicate items."""
        from django.core.management import call_command

        call_command("seed_food_items")
        first_count = FoodItem.objects.count()
        call_command("seed_food_items")
        self.assertEqual(FoodItem.objects.count(), first_count)

    def test_seed_reset_flag(self) -> None:
        """The --reset flag clears existing items before seeding."""
        from django.core.management import call_command

        _make_food()
        call_command("seed_food_items", reset=True)
        # The leftover custom item is removed, then reseeded catalog remains.
        self.assertNotIn(
            "White Rice",
            FoodItem.objects.values_list("name", flat=True).filter(
                name="White Rice",
            ),
        )
        self.assertGreaterEqual(FoodItem.objects.count(), 100)
