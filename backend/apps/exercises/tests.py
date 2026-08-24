"""Tests for the exercises app."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import captured_stdout
from rest_framework.test import APITestCase

from apps.exercises.models import Exercise, ExerciseCategory
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


class ExerciseModelTests(TestCase):
    """Unit tests for exercise models."""

    def setUp(self) -> None:
        """Create a tenant and category for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.category = ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Strength",
            description="Resistance training.",
            slug="strength",
        )

    def test_exercise_requires_tenant(self) -> None:
        """Saving an exercise without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Exercise.objects.create(
                name="Push-Up",
                category=self.category,
                muscle_groups=["chest"],
                equipment_needed=[],
                difficulty="beginner",
                instructions=["Press up"],
            )

    def test_category_requires_tenant(self) -> None:
        """Saving a category without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            ExerciseCategory.objects.create(
                name="Cardio",
                slug="cardio",
            )

    def test_category_slug_unique_within_tenant(self) -> None:
        """Category slugs are unique within a tenant but reusable across tenants."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        ExerciseCategory.objects.create(
            tenant=other_tenant,
            name="Strength",
            slug="strength",
        )
        self.assertEqual(
            ExerciseCategory.objects.for_tenant(self.tenant).count(),
            1,
        )
        self.assertEqual(
            ExerciseCategory.objects.for_tenant(other_tenant).count(),
            1,
        )

    def test_exercise_creation_defaults(self) -> None:
        """Exercise defaults for JSON fields and difficulty are sensible."""
        exercise = Exercise.objects.create(
            tenant=self.tenant,
            name="Squat",
            category=self.category,
            muscle_groups=["quadriceps"],
            equipment_needed=[],
            difficulty="intermediate",
            instructions=["Descend", "Ascend"],
        )
        self.assertEqual(exercise.difficulty, "intermediate")
        self.assertEqual(exercise.muscle_groups, ["quadriceps"])
        self.assertIsNone(exercise.media_url)
        self.assertEqual(exercise.tips, "")

    def test_exercise_tenant_isolation(self) -> None:
        """Exercises are scoped to their tenant."""
        exercise = Exercise.objects.create(
            tenant=self.tenant,
            name="Deadlift",
            category=self.category,
            muscle_groups=["hamstrings"],
            equipment_needed=["barbell"],
            difficulty="advanced",
            instructions=["Lift"],
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            Exercise.objects.for_tenant(self.tenant).first().id,
            exercise.id,
        )
        self.assertEqual(Exercise.objects.for_tenant(other_tenant).count(), 0)

    def test_str_representations(self) -> None:
        """String representations are human-readable."""
        self.assertEqual(str(self.category), "Strength")
        exercise = Exercise.objects.create(
            tenant=self.tenant,
            name="Push-Up",
            category=self.category,
        )
        self.assertEqual(str(exercise), "Push-Up")


class ExerciseSeedCommandTests(TestCase):
    """Tests for the seed_exercises management command."""

    def setUp(self) -> None:
        """Create a tenant for seeding."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_seed_populates_50_plus_exercises(self) -> None:
        """Seeding creates at least 50 exercises across categories."""
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        self.assertGreaterEqual(Exercise.objects.for_tenant(self.tenant).count(), 50)
        categories = ExerciseCategory.objects.for_tenant(self.tenant)
        self.assertGreaterEqual(categories.count(), 4)
        # Exercises reference valid tenant-scoped categories
        for exercise in Exercise.objects.for_tenant(self.tenant):
            self.assertEqual(exercise.category.tenant_id, self.tenant.id)
            self.assertGreater(len(exercise.muscle_groups), 0)
            self.assertGreater(len(exercise.instructions), 0)

    def test_seed_is_idempotent(self) -> None:
        """Running the seed command twice does not duplicate exercises."""
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        count_after_first = Exercise.objects.for_tenant(self.tenant).count()
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        self.assertEqual(
            Exercise.objects.for_tenant(self.tenant).count(),
            count_after_first,
        )

    def test_seed_reset_removes_existing(self) -> None:
        """The --reset flag clears prior exercises and categories."""
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id, reset=True)
        self.assertGreaterEqual(Exercise.objects.for_tenant(self.tenant).count(), 50)

    def test_seed_requires_existing_tenant(self) -> None:
        """Seeding for a missing tenant raises CommandError."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_exercises", tenant=999999)


class ExerciseCategoryAPITests(APITestCase):
    """Integration tests for exercise category endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_list_categories(self) -> None:
        """Owner can list categories."""
        ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Strength",
            slug="strength",
        )
        response = self.client.get("/api/v1/exercises/exercise-categories/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_category(self) -> None:
        """Owner can create a category."""
        response = self.client.post(
            "/api/v1/exercises/exercise-categories/",
            {"name": "Cardio", "slug": "cardio", "description": "Endurance."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Cardio")
        self.assertEqual(response.data["exercise_count"], 0)

    def test_retrieve_update_delete_category(self) -> None:
        """Owner can retrieve, update, and delete a category."""
        category = ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Mobility",
            slug="mobility",
        )
        response = self.client.get(
            f"/api/v1/exercises/exercise-categories/{category.id}/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Mobility")

        response = self.client.patch(
            f"/api/v1/exercises/exercise-categories/{category.id}/",
            {"name": "Movement"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        category.refresh_from_db()
        self.assertEqual(category.name, "Movement")

        response = self.client.delete(
            f"/api/v1/exercises/exercise-categories/{category.id}/",
        )
        self.assertEqual(response.status_code, 204)

    def test_category_tenant_isolation(self) -> None:
        """Categories from another tenant are not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_category = ExerciseCategory.objects.create(
            tenant=other_tenant,
            name="Strength",
            slug="strength",
        )
        response = self.client.get(
            f"/api/v1/exercises/exercise-categories/{other_category.id}/",
        )
        self.assertEqual(response.status_code, 404)

    def test_category_search(self) -> None:
        """Categories can be searched by name."""
        ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Strength",
            slug="strength",
        )
        ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Cardio",
            slug="cardio",
        )
        response = self.client.get(
            "/api/v1/exercises/exercise-categories/?search=strength",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Strength")


class ExerciseAPITests(APITestCase):
    """Integration tests for exercise endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, category, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.category = ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Strength",
            slug="strength",
        )

    def _make_exercise(
        self,
        name: str = "Push-Up",
        category=None,
        difficulty: str = "beginner",
        muscle_groups=None,
        equipment=None,
    ) -> Exercise:
        """Helper to create an exercise in the test tenant."""
        return Exercise.objects.create(
            tenant=self.tenant,
            name=name,
            category=category or self.category,
            muscle_groups=muscle_groups or ["chest", "triceps"],
            equipment_needed=equipment or [],
            difficulty=difficulty,
            instructions=["Step one", "Step two"],
        )

    def test_list_exercises(self) -> None:
        """Owner can list exercises."""
        self._make_exercise()
        response = self.client.get("/api/v1/exercises/exercises/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_exercise(self) -> None:
        """Owner can create an exercise."""
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "Squat",
                "category": self.category.id,
                "muscle_groups": ["quadriceps", "glutes"],
                "equipment_needed": ["barbell"],
                "difficulty": "intermediate",
                "instructions": ["Descend", "Ascend"],
                "tips": "Keep chest up.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Squat")
        self.assertEqual(response.data["category_name"], "Strength")
        self.assertEqual(response.data["muscle_groups"], ["quadriceps", "glutes"])

    def test_retrieve_update_delete_exercise(self) -> None:
        """Owner can retrieve, update, and delete an exercise."""
        exercise = self._make_exercise(name="Deadlift", difficulty="advanced")
        response = self.client.get(
            f"/api/v1/exercises/exercises/{exercise.id}/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Deadlift")

        response = self.client.patch(
            f"/api/v1/exercises/exercises/{exercise.id}/",
            {"difficulty": "beginner"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        exercise.refresh_from_db()
        self.assertEqual(exercise.difficulty, "beginner")

        response = self.client.delete(
            f"/api/v1/exercises/exercises/{exercise.id}/",
        )
        self.assertEqual(response.status_code, 204)

    def test_filter_exercises_by_category(self) -> None:
        """Exercises can be filtered by category."""
        other_cat = ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Cardio",
            slug="cardio",
        )
        self._make_exercise(name="Push-Up")
        self._make_exercise(name="Run", category=other_cat, muscle_groups=["legs"])
        response = self.client.get(
            f"/api/v1/exercises/exercises/?category={other_cat.id}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Run")

    def test_filter_exercise_by_difficulty(self) -> None:
        """Exercises can be filtered by difficulty."""
        self._make_exercise(name="Push-Up", difficulty="beginner")
        self._make_exercise(name="Deadlift", difficulty="advanced")
        response = self.client.get(
            "/api/v1/exercises/exercises/?difficulty=advanced",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Deadlift")

    def test_filter_exercise_by_muscle_group(self) -> None:
        """Exercises can be filtered by a muscle group in the JSON array."""
        self._make_exercise(name="Push-Up", muscle_groups=["chest", "triceps"])
        self._make_exercise(
            name="Leg Press",
            muscle_groups=["quadriceps", "glutes"],
        )
        response = self.client.get(
            "/api/v1/exercises/exercises/?muscle_group=chest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Push-Up")

    def test_filter_exercise_by_equipment(self) -> None:
        """Exercises can be filtered by an equipment item in the JSON array."""
        self._make_exercise(name="Push-Up", equipment=[])
        self._make_exercise(name="Bench Press", equipment=["barbell", "bench"])
        response = self.client.get(
            "/api/v1/exercises/exercises/?equipment_needed=barbell",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Bench Press")

    def test_search_exercise_by_name(self) -> None:
        """Exercises can be searched by name."""
        self._make_exercise(name="Squat")
        self._make_exercise(name="Lunge")
        response = self.client.get(
            "/api/v1/exercises/exercises/?search=squat",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Squat")

    def test_exercise_tenant_isolation(self) -> None:
        """Exercises from another tenant are not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_cat = ExerciseCategory.objects.create(
            tenant=other_tenant,
            name="Strength",
            slug="strength",
        )
        other_exercise = Exercise.objects.create(
            tenant=other_tenant,
            name="Other Press",
            category=other_cat,
        )
        response = self.client.get(
            f"/api/v1/exercises/exercises/{other_exercise.id}/",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_exercise_cross_tenant_category_rejected(self) -> None:
        """Creating an exercise with another tenant's category is rejected."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_cat = ExerciseCategory.objects.create(
            tenant=other_tenant,
            name="Strength",
            slug="strength",
        )
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "Bad",
                "category": other_cat.id,
                "muscle_groups": ["chest"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Go"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class ExercisePermissionTests(APITestCase):
    """Tests for role-based access to exercise endpoints."""

    def setUp(self) -> None:
        """Create two tenants, an owner, a customer, and a trainer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.category = ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Strength",
            slug="strength",
        )
        # Customer user.
        self.customer = User.objects.create_user(
            email="customer@local.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="Omer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer_token = issue_token(self.customer, self.tenant)
        # Trainer user.
        self.trainer = User.objects.create_user(
            email="trainer@local.test",
            password="F1tNati0n!",
            first_name="Train",
            last_name="Er",
            role=User.Role.TRAINER,
            tenant=self.tenant,
        )
        self.trainer_token = issue_token(self.trainer, self.tenant)

    def test_customer_can_view_exercises(self) -> None:
        """All authenticated users (including customers) can view exercises."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.customer_token.key}")
        response = self.client.get("/api/v1/exercises/exercises/")
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_create_exercise(self) -> None:
        """Customers cannot create exercises."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.customer_token.key}")
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "Push-Up",
                "category": self.category.id,
                "muscle_groups": ["chest"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Press"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_create_category(self) -> None:
        """Customers cannot create categories."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.customer_token.key}")
        response = self.client.post(
            "/api/v1/exercises/exercise-categories/",
            {"name": "Cardio", "slug": "cardio"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_trainer_can_create_exercise(self) -> None:
        """Trainers can create exercises."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.trainer_token.key}")
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "Trainer Exercise",
                "category": self.category.id,
                "muscle_groups": ["chest"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Press"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_trainer_can_edit_and_delete_exercise(self) -> None:
        """Trainers can edit and delete exercises."""
        exercise = Exercise.objects.create(
            tenant=self.tenant,
            name="Deadlift",
            category=self.category,
            muscle_groups=["back"],
            equipment_needed=["barbell"],
            difficulty="advanced",
            instructions=["Lift"],
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.trainer_token.key}")
        response = self.client.patch(
            f"/api/v1/exercises/exercises/{exercise.id}/",
            {"difficulty": "beginner"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.delete(
            f"/api/v1/exercises/exercises/{exercise.id}/",
        )
        self.assertEqual(response.status_code, 204)

    def test_unauthenticated_cannot_access(self) -> None:
        """Unauthenticated requests are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/exercises/exercises/")
        self.assertEqual(response.status_code, 401)

    def test_customer_tenant_isolation_forced_404(self) -> None:
        """Another tenant's exercise returns 404 (never leaks existence)."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_cat = ExerciseCategory.objects.create(
            tenant=other_tenant,
            name="Strength",
            slug="strength",
        )
        other_exercise = Exercise.objects.create(
            tenant=other_tenant,
            name="Other",
            category=other_cat,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.customer_token.key}")
        response = self.client.get(
            f"/api/v1/exercises/exercises/{other_exercise.id}/",
        )
        self.assertEqual(response.status_code, 404)
