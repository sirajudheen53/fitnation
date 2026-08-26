"""Tests for the workouts app: models, serializers, APIs, permissions, isolation."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.exercises.models import Exercise, ExerciseCategory
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token
from apps.workouts.models import (
    WorkoutAssignment,
    WorkoutDay,
    WorkoutExercise,
    WorkoutLog,
    WorkoutPlan,
)
from apps.workouts.serializers import (
    WorkoutDaySerializer,
    WorkoutExerciseSerializer,
    WorkoutPlanSerializer,
)

User = get_user_model()


def _make_category(tenant, name="Strength", slug="strength") -> ExerciseCategory:
    """Create an ExerciseCategory for a tenant."""
    return ExerciseCategory.objects.create(
        tenant=tenant,
        name=name,
        description="Resistance training.",
        slug=slug,
    )


def _make_exercise(tenant, category, name="Push-Up") -> Exercise:
    """Create an Exercise for a tenant."""
    return Exercise.objects.create(
        tenant=tenant,
        name=name,
        category=category,
        muscle_groups=["chest"],
        equipment_needed=[],
        difficulty="beginner",
        instructions=["Press up"],
    )


def _make_plan(tenant, user=None, **overrides) -> WorkoutPlan:
    """Create a WorkoutPlan with sensible defaults."""
    defaults = {
        "name": "Strength Plan",
        "description": "A strength program.",
        "goal": WorkoutPlan.Goal.STRENGTH,
        "difficulty": WorkoutPlan.Difficulty.INTERMEDIATE,
        "duration_weeks": 4,
        "is_template": False,
        "created_by": user,
    }
    defaults.update(overrides)
    return WorkoutPlan.objects.create(tenant=tenant, **defaults)


class WorkoutPlanModelTests(TestCase):
    """Unit tests for the WorkoutPlan model."""

    def setUp(self) -> None:
        """Create a tenant for plan tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_workout_plan_requires_tenant(self) -> None:
        """Saving a WorkoutPlan without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            WorkoutPlan.objects.create(name="No Tenant Plan")

    def test_workout_plan_str(self) -> None:
        """The plan string includes name and goal."""
        plan = _make_plan(self.tenant)
        self.assertEqual(str(plan), "Strength Plan (strength)")

    def test_workout_plan_defaults(self) -> None:
        """WorkoutPlan defaults are sensible."""
        plan = _make_plan(self.tenant)
        self.assertFalse(plan.is_template)
        self.assertEqual(plan.duration_weeks, 4)
        self.assertEqual(plan.difficulty, WorkoutPlan.Difficulty.INTERMEDIATE)


class WorkoutDayModelTests(TestCase):
    """Unit tests for the WorkoutDay model."""

    def setUp(self) -> None:
        """Create a tenant and plan."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.plan = _make_plan(self.tenant)

    def test_workout_day_requires_tenant(self) -> None:
        """Saving a WorkoutDay without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            WorkoutDay.objects.create(workout_plan=self.plan, day_of_week="monday")

    def test_workout_day_str(self) -> None:
        """The day string includes plan and focus."""
        day = WorkoutDay.objects.create(
            tenant=self.tenant,
            workout_plan=self.plan,
            day_of_week=WorkoutDay.DayOfWeek.MONDAY,
            focus="Push Day",
        )
        self.assertEqual(str(day), "Strength Plan — Push Day")


class WorkoutExerciseModelTests(TestCase):
    """Unit tests for the WorkoutExercise model."""

    def setUp(self) -> None:
        """Create a tenant, plan, day, and exercise."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.plan = _make_plan(self.tenant)
        self.day = WorkoutDay.objects.create(
            tenant=self.tenant,
            workout_plan=self.plan,
            day_of_week=WorkoutDay.DayOfWeek.MONDAY,
        )
        self.category = _make_category(self.tenant)
        self.exercise = _make_exercise(self.tenant, self.category)

    def test_workout_exercise_requires_tenant(self) -> None:
        """Saving a WorkoutExercise without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            WorkoutExercise.objects.create(
                workout_day=self.day,
                exercise=self.exercise,
                sets=3,
                reps="8-12",
            )

    def test_workout_exercise_str(self) -> None:
        """The exercise string includes name and prescription."""
        we = WorkoutExercise.objects.create(
            tenant=self.tenant,
            workout_day=self.day,
            exercise=self.exercise,
            sets=3,
            reps="8-12",
        )
        self.assertEqual(str(we), "Push-Up × 3×8-12")

    def test_workout_exercise_clean_rejects_invalid_rpe(self) -> None:
        """RPE outside 1-10 is rejected by clean()."""
        we = WorkoutExercise(
            tenant=self.tenant,
            workout_day=self.day,
            exercise=self.exercise,
            rpe=11,
        )
        with self.assertRaises(Exception):
            we.full_clean()


class WorkoutAssignmentModelTests(TestCase):
    """Unit tests for the WorkoutAssignment model."""

    def setUp(self) -> None:
        """Create a tenant, plan, and customer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.plan = _make_plan(self.tenant)
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
        assignment = WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
        )
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.start_date, date.today())

    def test_assignment_str(self) -> None:
        """The assignment string includes customer and plan."""
        assignment = WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
        )
        self.assertEqual(str(assignment), "Customer ← Strength Plan")


class WorkoutLogModelTests(TestCase):
    """Unit tests for the WorkoutLog model."""

    def setUp(self) -> None:
        """Create a tenant, plan, day, exercise, and customer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.plan = _make_plan(self.tenant)
        self.day = WorkoutDay.objects.create(
            tenant=self.tenant,
            workout_plan=self.plan,
            day_of_week=WorkoutDay.DayOfWeek.MONDAY,
        )
        self.category = _make_category(self.tenant)
        self.exercise = _make_exercise(self.tenant, self.category)
        self.we = WorkoutExercise.objects.create(
            tenant=self.tenant,
            workout_day=self.day,
            exercise=self.exercise,
            sets=3,
            reps="8-12",
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

    def test_workout_log_requires_tenant(self) -> None:
        """Saving a WorkoutLog without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            WorkoutLog.objects.create(
                customer=self.customer,
                workout_exercise=self.we,
                workout_day=self.day,
                set_number=1,
            )

    def test_workout_log_str(self) -> None:
        """The log string includes customer and exercise."""
        log = WorkoutLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_exercise=self.we,
            workout_day=self.day,
            set_number=1,
            actual_reps=10,
            actual_weight=50.0,
        )
        self.assertIn("Customer", str(log))
        self.assertIn("Push-Up", str(log))


class WorkoutSerializerTests(TestCase):
    """Unit tests for workout serializers."""

    def setUp(self) -> None:
        """Create a tenant, plan, day, exercise, and customer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.plan = _make_plan(self.tenant)
        self.day = WorkoutDay.objects.create(
            tenant=self.tenant,
            workout_plan=self.plan,
            day_of_week=WorkoutDay.DayOfWeek.MONDAY,
            focus="Push Day",
        )
        self.category = _make_category(self.tenant)
        self.exercise = _make_exercise(self.tenant, self.category)
        self.we = WorkoutExercise.objects.create(
            tenant=self.tenant,
            workout_day=self.day,
            exercise=self.exercise,
            sets=3,
            reps="8-12",
        )

    def test_workout_plan_serializer_nested(self) -> None:
        """The plan serializer includes nested days and exercises."""
        data = WorkoutPlanSerializer(self.plan).data
        self.assertEqual(data["name"], "Strength Plan")
        self.assertEqual(len(data["days"]), 1)
        self.assertEqual(len(data["days"][0]["exercises"]), 1)
        self.assertEqual(data["days"][0]["exercises"][0]["exercise_name"], "Push-Up")

    def test_workout_day_serializer_nested(self) -> None:
        """The day serializer includes nested exercises."""
        data = WorkoutDaySerializer(self.day).data
        self.assertEqual(data["focus"], "Push Day")
        self.assertEqual(len(data["exercises"]), 1)

    def test_workout_exercise_serializer_inline_details(self) -> None:
        """The exercise serializer includes inline exercise details."""
        data = WorkoutExerciseSerializer(self.we).data
        self.assertEqual(data["exercise_name"], "Push-Up")
        self.assertEqual(data["exercise_details"]["name"], "Push-Up")
        self.assertEqual(data["sets"], 3)

    def test_workout_exercise_serializer_rejects_invalid_rpe(self) -> None:
        """RPE outside 1-10 is rejected by the serializer."""
        serializer = WorkoutExerciseSerializer(
            data={
                "workout_day": self.day.id,
                "exercise": self.exercise.id,
                "sets": 3,
                "reps": "8-12",
                "rpe": 12,
            },
            context={"request": None},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("rpe", serializer.errors)


class WorkoutAPIBase(APITestCase):
    """Shared base for workout API tests."""

    def setUp(self) -> None:
        """Create a tenant, owner, customer, exercise, and plan."""
        self.tenant = provision_tenant("Iron Peak", contact_email="owner@workout.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@workout.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.category = _make_category(self.tenant)
        self.exercise = _make_exercise(self.tenant, self.category)
        self.exercise2 = _make_exercise(self.tenant, self.category, name="Squat")

        self.plan = _make_plan(self.tenant, user=self.owner)
        self.day = WorkoutDay.objects.create(
            tenant=self.tenant,
            workout_plan=self.plan,
            day_of_week=WorkoutDay.DayOfWeek.MONDAY,
            focus="Push Day",
        )
        self.we = WorkoutExercise.objects.create(
            tenant=self.tenant,
            workout_day=self.day,
            exercise=self.exercise,
            sets=3,
            reps="8-12",
        )

        self.customer_user = User.objects.create_user(
            email="cust@workout.test",
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
            email="cust@workout.test",
        )


class WorkoutPlanAPITests(WorkoutAPIBase):
    """Tests for the workout plan endpoints."""

    def test_list_workout_plans(self) -> None:
        """Authenticated users can list workout plans."""
        response = self.client.get("/api/v1/workouts/workout-plans/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_workout_plans_by_goal(self) -> None:
        """Workout plans can be filtered by goal."""
        _make_plan(self.tenant, name="Cardio Plan", goal=WorkoutPlan.Goal.ENDURANCE)
        response = self.client.get("/api/v1/workouts/workout-plans/?goal=endurance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Cardio Plan")

    def test_filter_workout_plans_by_difficulty(self) -> None:
        """Workout plans can be filtered by difficulty."""
        _make_plan(self.tenant, name="Easy Plan", difficulty=WorkoutPlan.Difficulty.BEGINNER)
        response = self.client.get("/api/v1/workouts/workout-plans/?difficulty=beginner")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Easy Plan")

    def test_create_workout_plan_with_nested_days_and_exercises(self) -> None:
        """A complete plan with days and exercises can be created in one POST."""
        payload = {
            "name": "Full Body Plan",
            "description": "A full body program.",
            "goal": "general_fitness",
            "difficulty": "beginner",
            "duration_weeks": 6,
            "days": [
                {
                    "day_of_week": "monday",
                    "focus": "Full Body",
                    "exercises": [
                        {
                            "exercise": self.exercise.id,
                            "sets": 3,
                            "reps": "10-12",
                            "rest_seconds": 60,
                            "order": 1,
                        },
                        {
                            "exercise": self.exercise2.id,
                            "sets": 4,
                            "reps": "8",
                            "rest_seconds": 90,
                            "order": 2,
                        },
                    ],
                }
            ],
        }
        response = self.client.post("/api/v1/workouts/workout-plans/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Full Body Plan")
        self.assertEqual(len(response.data["days"]), 1)
        self.assertEqual(len(response.data["days"][0]["exercises"]), 2)
        self.assertEqual(WorkoutPlan.objects.for_tenant(self.tenant).count(), 2)

    def test_retrieve_workout_plan(self) -> None:
        """A workout plan can be retrieved with nested days."""
        response = self.client.get(f"/api/v1/workouts/workout-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Strength Plan")
        self.assertEqual(len(response.data["days"]), 1)

    def test_update_workout_plan(self) -> None:
        """A workout plan can be updated."""
        response = self.client.patch(
            f"/api/v1/workouts/workout-plans/{self.plan.id}/",
            {"name": "Updated Plan"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Updated Plan")

    def test_delete_workout_plan(self) -> None:
        """A workout plan can be deleted."""
        response = self.client.delete(f"/api/v1/workouts/workout-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(WorkoutPlan.objects.for_tenant(self.tenant).count(), 0)

    def test_duplicate_workout_plan(self) -> None:
        """A workout plan can be duplicated as a template."""
        response = self.client.post(f"/api/v1/workouts/workout-plans/{self.plan.id}/duplicate/")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_template"])
        self.assertEqual(response.data["name"], "Strength Plan (copy)")
        self.assertEqual(len(response.data["days"]), 1)
        self.assertEqual(len(response.data["days"][0]["exercises"]), 1)


class WorkoutDayExerciseAPITests(WorkoutAPIBase):
    """Tests for the workout day and exercise endpoints."""

    def test_create_workout_day(self) -> None:
        """A workout day can be created under a plan."""
        response = self.client.post(
            "/api/v1/workouts/workout-days/",
            {
                "workout_plan": self.plan.id,
                "day_of_week": "tuesday",
                "focus": "Leg Day",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["focus"], "Leg Day")

    def test_list_workout_days_by_plan(self) -> None:
        """Workout days can be filtered by plan."""
        response = self.client.get(f"/api/v1/workouts/workout-days/?workout_plan={self.plan.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_update_workout_day(self) -> None:
        """A workout day can be updated."""
        response = self.client.patch(
            f"/api/v1/workouts/workout-days/{self.day.id}/",
            {"focus": "Chest Day"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["focus"], "Chest Day")

    def test_delete_workout_day(self) -> None:
        """A workout day can be deleted."""
        response = self.client.delete(f"/api/v1/workouts/workout-days/{self.day.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(WorkoutDay.objects.for_tenant(self.tenant).count(), 0)

    def test_create_workout_exercise(self) -> None:
        """A workout exercise can be created under a day."""
        response = self.client.post(
            "/api/v1/workouts/workout-exercises/",
            {
                "workout_day": self.day.id,
                "exercise": self.exercise2.id,
                "sets": 4,
                "reps": "6-8",
                "rest_seconds": 90,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["exercise_name"], "Squat")

    def test_list_workout_exercises_by_day(self) -> None:
        """Workout exercises can be filtered by day."""
        response = self.client.get(f"/api/v1/workouts/workout-exercises/?workout_day={self.day.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_update_workout_exercise(self) -> None:
        """A workout exercise can be updated."""
        response = self.client.patch(
            f"/api/v1/workouts/workout-exercises/{self.we.id}/",
            {"sets": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sets"], 5)

    def test_delete_workout_exercise(self) -> None:
        """A workout exercise can be deleted."""
        response = self.client.delete(f"/api/v1/workouts/workout-exercises/{self.we.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(WorkoutExercise.objects.for_tenant(self.tenant).count(), 0)


class WorkoutAssignmentAPITests(WorkoutAPIBase):
    """Tests for the workout assignment endpoints."""

    def test_assign_workout_plan_to_customer(self) -> None:
        """A workout plan can be assigned to a customer."""
        response = self.client.post(
            "/api/v1/workouts/workout-assignments/",
            {
                "customer": self.customer.id,
                "workout_plan": self.plan.id,
                "start_date": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["customer_name"], "Customer One")
        self.assertEqual(response.data["workout_plan_name"], "Strength Plan")
        self.assertEqual(response.data["assigned_by"], self.owner.id)

    def test_list_assignments_by_customer(self) -> None:
        """Assignments can be filtered by customer."""
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
        )
        response = self.client.get(
            f"/api/v1/workouts/workout-assignments/?customer={self.customer.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_active_assignment_endpoint(self) -> None:
        """The active endpoint returns a customer's active assignment."""
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
            is_active=True,
        )
        response = self.client.get(
            f"/api/v1/workouts/workout-assignments/active/?customer={self.customer.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_update_assignment(self) -> None:
        """An assignment can be updated."""
        assignment = WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
        )
        response = self.client.patch(
            f"/api/v1/workouts/workout-assignments/{assignment.id}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])

    def test_delete_assignment(self) -> None:
        """An assignment can be deleted."""
        assignment = WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
        )
        response = self.client.delete(f"/api/v1/workouts/workout-assignments/{assignment.id}/")
        self.assertEqual(response.status_code, 204)


class WorkoutLogAPITests(WorkoutAPIBase):
    """Tests for the workout log endpoints and progress tracking."""

    def test_log_workout_set(self) -> None:
        """A customer's workout set can be logged."""
        response = self.client.post(
            "/api/v1/workouts/workout-logs/",
            {
                "customer": self.customer.id,
                "workout_exercise": self.we.id,
                "workout_day": self.day.id,
                "date_completed": "2026-01-05",
                "set_number": 1,
                "actual_reps": 10,
                "actual_weight": 50.0,
                "actual_rest_seconds": 60,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["exercise_name"], "Push-Up")
        self.assertEqual(response.data["actual_reps"], 10)

    def test_list_logs_by_customer(self) -> None:
        """Logs can be filtered by customer."""
        WorkoutLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_exercise=self.we,
            workout_day=self.day,
            set_number=1,
            actual_reps=10,
        )
        response = self.client.get(f"/api/v1/workouts/workout-logs/?customer={self.customer.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_logs_by_date_range(self) -> None:
        """Logs can be filtered by date range for progress tracking."""
        WorkoutLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_exercise=self.we,
            workout_day=self.day,
            date_completed="2026-01-05",
            set_number=1,
            actual_reps=10,
        )
        WorkoutLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_exercise=self.we,
            workout_day=self.day,
            date_completed="2026-02-10",
            set_number=1,
            actual_reps=12,
        )
        response = self.client.get(
            f"/api/v1/workouts/workout-logs/?customer={self.customer.id}"
            "&date_from=2026-01-01&date_to=2026-01-31"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["actual_reps"], 10)

    def test_update_log(self) -> None:
        """A workout log can be updated."""
        log = WorkoutLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_exercise=self.we,
            workout_day=self.day,
            set_number=1,
            actual_reps=10,
        )
        response = self.client.patch(
            f"/api/v1/workouts/workout-logs/{log.id}/",
            {"actual_reps": 12},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["actual_reps"], 12)

    def test_delete_log(self) -> None:
        """A workout log can be deleted."""
        log = WorkoutLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_exercise=self.we,
            workout_day=self.day,
            set_number=1,
        )
        response = self.client.delete(f"/api/v1/workouts/workout-logs/{log.id}/")
        self.assertEqual(response.status_code, 204)


class WorkoutPermissionsTests(WorkoutAPIBase):
    """Tests for workout role-based permissions and tenant isolation."""

    def test_customer_can_view_assigned_plan(self) -> None:
        """A customer can view a plan they are assigned to."""
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
            is_active=True,
        )
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/workouts/workout-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_create_plan(self) -> None:
        """A customer cannot create a workout plan."""
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            "/api/v1/workouts/workout-plans/",
            {"name": "Hack Plan"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_can_log_own_workout(self) -> None:
        """A customer can log their own workout set."""
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            "/api/v1/workouts/workout-logs/",
            {
                "customer": self.customer.id,
                "workout_exercise": self.we.id,
                "workout_day": self.day.id,
                "set_number": 1,
                "actual_reps": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_customer_cannot_log_other_customer(self) -> None:
        """A customer cannot log a workout for another customer."""
        other_user = User.objects.create_user(
            email="other@workout.test",
            password="F1tNati0n!",
            first_name="Other",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        other_customer = Customer.objects.create(
            tenant=self.tenant,
            user=other_user,
            name="Other Customer",
            email="other@workout.test",
        )
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            "/api/v1/workouts/workout-logs/",
            {
                "customer": other_customer.id,
                "workout_exercise": self.we.id,
                "workout_day": self.day.id,
                "set_number": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_tenant_isolation_plan(self) -> None:
        """A plan from another tenant is not accessible."""
        other = provision_tenant("Other Gym", contact_email="other@workout.test")
        other_owner = create_owner_user(
            tenant=other,
            email="other@workout.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        token = issue_token(other_owner, other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/workouts/workout-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 404)

    def test_tenant_isolation_assignment(self) -> None:
        """An assignment from another tenant is not accessible."""
        other = provision_tenant("Other Gym", contact_email="other2@workout.test")
        other_owner = create_owner_user(
            tenant=other,
            email="other2@workout.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        token = issue_token(other_owner, other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/v1/workouts/workout-assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 0)

    def test_cross_tenant_exercise_rejected(self) -> None:
        """Creating a plan with another tenant's exercise is rejected."""
        other = provision_tenant("Other Gym", contact_email="other3@workout.test")
        other_category = _make_category(other, name="Cardio", slug="cardio")
        other_exercise = _make_exercise(other, other_category, name="Other Move")
        response = self.client.post(
            "/api/v1/workouts/workout-plans/",
            {
                "name": "Bad Plan",
                "days": [
                    {
                        "day_of_week": "monday",
                        "exercises": [{"exercise": other_exercise.id, "sets": 3}],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class WorkoutExtendedAPITests(WorkoutAPIBase):
    """Extended tests for nested writes and full CRUD flows."""

    def test_full_nested_plan_update(self) -> None:
        """A plan can be updated with full nested days/exercises replacement."""
        payload = {
            "name": "Updated Full Plan",
            "days": [
                {
                    "day_of_week": "wednesday",
                    "focus": "Pull Day",
                    "exercises": [
                        {
                            "exercise": self.exercise2.id,
                            "sets": 4,
                            "reps": "6-8",
                            "order": 1,
                        }
                    ],
                }
            ],
        }
        response = self.client.put(
            f"/api/v1/workouts/workout-plans/{self.plan.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Updated Full Plan")
        self.assertEqual(len(response.data["days"]), 1)
        self.assertEqual(response.data["days"][0]["focus"], "Pull Day")
        self.assertEqual(len(response.data["days"][0]["exercises"]), 1)

    def test_customer_active_assignment_endpoint(self) -> None:
        """A customer can fetch their own active assignment without a customer param."""
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
            is_active=True,
        )
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/v1/workouts/workout-assignments/active/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_customer_can_view_assigned_plan_days(self) -> None:
        """A customer can view days of an assigned plan."""
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            workout_plan=self.plan,
            is_active=True,
        )
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/workouts/workout-days/{self.day.id}/")
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_view_unassigned_plan(self) -> None:
        """A customer cannot view a plan they are not assigned to."""
        token = issue_token(self.customer_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"/api/v1/workouts/workout-plans/{self.plan.id}/")
        self.assertEqual(response.status_code, 403)

    def test_duplicate_preserves_exercises(self) -> None:
        """Duplicating a plan preserves its exercises."""
        response = self.client.post(f"/api/v1/workouts/workout-plans/{self.plan.id}/duplicate/")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["days"][0]["exercises"]), 1)
        self.assertEqual(
            response.data["days"][0]["exercises"][0]["exercise_name"],
            "Push-Up",
        )
