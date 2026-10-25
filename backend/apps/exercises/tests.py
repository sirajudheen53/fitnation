"""Tests for the exercises app."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import captured_stdout
from rest_framework.test import APITestCase

from apps.exercises.catalogue import DEFAULT_CATEGORIES, EXERCISE_CATALOGUE
from apps.exercises.models import Exercise, ExerciseCategory
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


class ExerciseModelTests(TestCase):
    """Unit tests for exercise models."""

    def setUp(self) -> None:
        """Create a tenant and category for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test", seed_exercises=False)
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test", seed_exercises=False)
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test", seed_exercises=False)
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
        """Create a tenant without the auto-seed so the command is under test."""
        self.tenant = provision_tenant(
            name="Iron Peak",
            contact_email="owner@local.test",
            seed_exercises=False,
        )

    def test_seed_populates_full_catalogue(self) -> None:
        """Seeding creates every catalogue exercise across the default categories."""
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        self.assertEqual(
            Exercise.objects.for_tenant(self.tenant).count(),
            len(EXERCISE_CATALOGUE),
        )
        categories = ExerciseCategory.objects.for_tenant(self.tenant)
        self.assertGreaterEqual(categories.count(), len(DEFAULT_CATEGORIES))
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

    def test_seed_catalogue_integrity(self) -> None:
        """The catalogue itself has unique names and known categories."""
        names = [item["name"] for item in EXERCISE_CATALOGUE]
        self.assertEqual(len(names), len(set(names)))
        for item in EXERCISE_CATALOGUE:
            self.assertIn(item["category"], DEFAULT_CATEGORIES)
            self.assertGreaterEqual(len(item["instructions"]), 2)

    def test_seed_updates_drifted_rows(self) -> None:
        """Re-seeding refreshes catalogue rows that drifted from the defaults."""
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        push_up = Exercise.objects.for_tenant(self.tenant).get(name="Push-Up")
        push_up.tips = ""
        push_up.difficulty = "advanced"
        push_up.save(update_fields=["tips", "difficulty"])

        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)

        push_up.refresh_from_db()
        expected = next(i for i in EXERCISE_CATALOGUE if i["name"] == "Push-Up")
        self.assertEqual(push_up.difficulty, expected["difficulty"])
        self.assertEqual(push_up.tips, expected.get("tips", ""))

    def test_seed_preserves_custom_rows(self) -> None:
        """Re-seeding never deletes or overwrites tenant-created exercises."""
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)
        rehab_category = ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Rehab",
            slug="rehab",
        )
        custom = Exercise.objects.create(
            tenant=self.tenant,
            name="Owner Special Move",
            category=rehab_category,
            muscle_groups=["shoulders"],
            equipment_needed=["resistance band"],
            difficulty="beginner",
            instructions=["Do the move"],
        )

        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id)

        custom.refresh_from_db()
        self.assertEqual(custom.name, "Owner Special Move")
        self.assertEqual(custom.category_id, rehab_category.id)
        self.assertEqual(Exercise.objects.for_tenant(self.tenant).count(), len(EXERCISE_CATALOGUE) + 1)
        # The custom category is left alone too.
        self.assertTrue(ExerciseCategory.objects.filter(tenant=self.tenant, slug="rehab").exists())

    def test_seed_reset_removes_existing(self) -> None:
        """The --reset flag clears prior exercises and categories."""
        ExerciseCategory.objects.create(
            tenant=self.tenant,
            name="Rehab",
            slug="rehab",
        )
        with captured_stdout():
            call_command("seed_exercises", tenant=self.tenant.id, reset=True)
        self.assertEqual(
            Exercise.objects.for_tenant(self.tenant).count(),
            len(EXERCISE_CATALOGUE),
        )
        self.assertFalse(ExerciseCategory.objects.filter(tenant=self.tenant, slug="rehab").exists())

    def test_seed_requires_existing_tenant(self) -> None:
        """Seeding for a missing tenant raises CommandError."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_exercises", tenant=999999)


class ProvisionTenantSeedTests(TestCase):
    """Every new gym starts with the common exercise catalogue (ticket #75)."""

    def test_provision_tenant_seeds_catalogue(self) -> None:
        """Default provisioning populates the full catalogue for the new gym."""
        tenant = provision_tenant(name="Fresh Gym", contact_email="fresh@local.test")
        self.assertEqual(
            Exercise.objects.for_tenant(tenant).count(),
            len(EXERCISE_CATALOGUE),
        )
        self.assertEqual(
            ExerciseCategory.objects.for_tenant(tenant).filter(slug__in=DEFAULT_CATEGORIES).count(),
            len(DEFAULT_CATEGORIES),
        )
        for exercise in Exercise.objects.for_tenant(tenant):
            self.assertEqual(exercise.category.tenant_id, tenant.id)

    def test_provision_tenant_seed_opt_out(self) -> None:
        """Provisioning with seed_exercises=False leaves the library empty."""
        tenant = provision_tenant(
            name="Bare Gym",
            contact_email="bare@local.test",
            seed_exercises=False,
        )
        self.assertEqual(Exercise.objects.for_tenant(tenant).count(), 0)
        self.assertEqual(ExerciseCategory.objects.for_tenant(tenant).count(), 0)


class ExerciseCategoryAPITests(APITestCase):
    """Integration tests for exercise category endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test", seed_exercises=False)
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test", seed_exercises=False)
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
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test", seed_exercises=False)
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

    def test_create_exercise_duplicate_name_rejected(self) -> None:
        """Duplicate exercise names within the tenant are rejected (case-insensitive)."""
        self._make_exercise(name="Push-Up")
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "push-up ",
                "category": self.category.id,
                "muscle_groups": ["chest"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Press"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data))

    def test_create_exercise_name_is_trimmed(self) -> None:
        """Names are stored trimmed, so whitespace-only duplicates are the same name."""
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "  Squat  ",
                "category": self.category.id,
                "muscle_groups": ["quadriceps"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Descend", "Ascend"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Squat")

    def test_update_exercise_keeping_own_name_ok(self) -> None:
        """Editing an exercise without renaming it is not flagged as a duplicate."""
        exercise = self._make_exercise(name="Push-Up")
        response = self.client.patch(
            f"/api/v1/exercises/exercises/{exercise.id}/",
            {"name": "Push-Up", "difficulty": "advanced"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Push-Up")

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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test", seed_exercises=False)
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test", seed_exercises=False)
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
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test", seed_exercises=False)
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test", seed_exercises=False)
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


class SeededListingAPITests(APITestCase):
    """The gym-owner experience in an auto-seeded library (default provisioning)."""

    def setUp(self) -> None:
        """Create an owner whose tenant got the default catalogue at provisioning."""
        self.tenant = provision_tenant(name="Hash Fit", contact_email="owner@hashfit.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@hashfit.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Hash Fit Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_owner_sees_catalogue_and_creation_appears_in_list(self) -> None:
        """A provisioned gym lists the catalogue; a created exercise joins the list."""
        response = self.client.get("/api/v1/exercises/exercises/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], len(EXERCISE_CATALOGUE))

        strength = ExerciseCategory.objects.for_tenant(self.tenant).get(slug="strength")
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "Fitness Test Move",
                "category": strength.id,
                "muscle_groups": ["chest"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Step one", "Step two"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get("/api/v1/exercises/exercises/")
        self.assertEqual(response.data["count"], len(EXERCISE_CATALOGUE) + 1)
        response = self.client.get("/api/v1/exercises/exercises/?search=fitness test")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Fitness Test Move")

    def test_owner_cannot_recreate_catalogue_name(self) -> None:
        """Creating a catalogue duplicate is rejected even in a seeded library."""
        strength = ExerciseCategory.objects.for_tenant(self.tenant).get(slug="strength")
        response = self.client.post(
            "/api/v1/exercises/exercises/",
            {
                "name": "push-up",
                "category": strength.id,
                "muscle_groups": ["chest"],
                "equipment_needed": [],
                "difficulty": "beginner",
                "instructions": ["Press"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data))

    def test_owner_can_create_category(self) -> None:
        """The owner can add custom categories alongside the defaults."""
        response = self.client.post(
            "/api/v1/exercises/exercise-categories/",
            {"name": "Rehab", "slug": "rehab", "description": "Recovery work."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["exercise_count"], 0)
