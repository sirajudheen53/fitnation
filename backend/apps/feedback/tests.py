"""Tests for the feedback app (FBOS-015)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.feedback.models import Feedback, FeedbackResponse, FeedbackSurvey
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, create_user, issue_token

User = get_user_model()


def make_customer_user(tenant, email):
    """Create a customer user plus its customer profile within a tenant."""
    return create_user(
        tenant=tenant,
        email=email,
        first_name="Customer",
        last_name="One",
        role=User.Role.CUSTOMER,
    )


class FeedbackModelTests(TestCase):
    """Unit tests for feedback models."""

    def setUp(self) -> None:
        """Create a tenant and customer for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.user = make_customer_user(self.tenant, "c@local.test")
        self.customer = self.user.customer_profile

    def test_feedback_requires_tenant(self) -> None:
        """Creating feedback without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Feedback.objects.create(
                customer=self.customer,
                rating=5,
                category=Feedback.Category.WORKOUT,
                comment="Great!",
            )

    def test_feedback_creates_successfully(self) -> None:
        """A feedback record persists with default values."""
        feedback = Feedback.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            rating=4,
            category=Feedback.Category.FACILITY,
            comment="Clean gym.",
        )
        self.assertEqual(feedback.rating, 4)
        self.assertFalse(feedback.is_anonymous)
        self.assertIsNone(feedback.response)
        self.assertEqual(str(feedback), "Feedback (4/5) by Customer One")

    def test_feedback_category_choices(self) -> None:
        """All expected categories are valid choices."""
        for choice in Feedback.Category.values:
            self.assertIn(
                choice,
                ["workout", "diet", "trainer", "facility", "app"],
            )

    def test_survey_and_response(self) -> None:
        """Surveys and responses can be created and linked."""
        survey = FeedbackSurvey.objects.create(
            tenant=self.tenant,
            name="Quarterly Check-in",
            questions=[
                {
                    "question_text": "Rate your experience",
                    "question_type": "rating",
                    "choices": [],
                }
            ],
        )
        response = FeedbackResponse.objects.create(
            tenant=self.tenant,
            survey=survey,
            customer=self.customer,
            answers={"0": 5},
        )
        self.assertEqual(survey.responses.count(), 1)
        self.assertEqual(response.survey, survey)
        self.assertEqual(response.answers, {"0": 5})

    def test_feedback_tenant_isolation(self) -> None:
        """Feedback is scoped to its tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_user = make_customer_user(other_tenant, "other@local.test")
        Feedback.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            rating=5,
        )
        Feedback.objects.create(
            tenant=other_tenant,
            customer=other_user.customer_profile,
            rating=3,
        )
        self.assertEqual(Feedback.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Feedback.objects.for_tenant(other_tenant).count(), 1)


class FeedbackAPITests(APITestCase):
    """Integration tests for feedback endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, branch, and auth tokens."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.customer_user = make_customer_user(self.tenant, "cust@local.test")
        self.customer = self.customer_user.customer_profile
        self.customer_token = issue_token(self.customer_user, self.tenant)

    def _auth(self, token) -> None:
        """Set the client auth header to the given token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _create_feedback(self, **overrides) -> Feedback:
        """Create a feedback record for the default customer."""
        data = {
            "tenant": self.tenant,
            "customer": self.customer,
            "rating": 5,
            "category": Feedback.Category.TRAINER,
            "comment": "Coach is excellent!",
        }
        data.update(overrides)
        return Feedback.objects.create(**data)

    def test_customer_submits_feedback(self) -> None:
        """A customer can submit their own feedback."""
        self._auth(self.customer_token)
        response = self.client.post(
            "/api/v1/feedback/feedback/",
            {"rating": 5, "category": "trainer", "comment": "Great coach"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["customer"], self.customer.id)
        self.assertEqual(
            Feedback.objects.for_tenant(self.tenant).filter(customer=self.customer).count(),
            1,
        )

    def test_customer_sees_only_own_feedback(self) -> None:
        """A customer cannot see other customers' feedback."""
        other_user = make_customer_user(self.tenant, "other@local.test")
        self._create_feedback()
        Feedback.objects.create(
            tenant=self.tenant,
            customer=other_user.customer_profile,
            rating=2,
            comment="Other feedback",
        )
        self._auth(self.customer_token)
        response = self.client.get("/api/v1/feedback/feedback/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_owner_sees_all_feedback(self) -> None:
        """Owners can view all feedback in the tenant."""
        self._create_feedback()
        self._auth(self.owner_token)
        response = self.client.get("/api/v1/feedback/feedback/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_trainer_can_view_all_and_respond(self) -> None:
        """Trainers can view all feedback and post responses."""
        trainer_user = create_user(
            tenant=self.tenant,
            email="trainer@local.test",
            first_name="Coach",
            last_name="One",
            role=User.Role.TRAINER,
        )
        trainer_token = issue_token(trainer_user, self.tenant)
        feedback = self._create_feedback()

        self._auth(trainer_token)
        response = self.client.get("/api/v1/feedback/feedback/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

        response = self.client.post(
            f"/api/v1/feedback/feedback/{feedback.id}/respond/",
            {"response": "Coach response"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        feedback.refresh_from_db()
        self.assertEqual(feedback.response, "Coach response")

    def test_manager_can_view_all_feedback(self) -> None:
        """Managers can view all feedback in the tenant."""
        manager_user = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Mgr",
            last_name="One",
            role=User.Role.MANAGER,
        )
        manager_token = issue_token(manager_user, self.tenant)
        self._create_feedback()
        self._auth(manager_token)
        response = self.client.get("/api/v1/feedback/feedback/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_owner_responds_to_feedback(self) -> None:
        """Owners can post a response to feedback."""
        feedback = self._create_feedback()
        self._auth(self.owner_token)
        response = self.client.post(
            f"/api/v1/feedback/feedback/{feedback.id}/respond/",
            {"response": "Thanks for the feedback!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        feedback.refresh_from_db()
        self.assertEqual(feedback.response, "Thanks for the feedback!")
        self.assertEqual(feedback.response_by, self.owner)

    def test_owner_respond_requires_text(self) -> None:
        """A response without text returns a 400."""
        feedback = self._create_feedback()
        self._auth(self.owner_token)
        response = self.client.post(
            f"/api/v1/feedback/feedback/{feedback.id}/respond/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_owner_can_update_feedback(self) -> None:
        """Owners can edit feedback records."""
        feedback = self._create_feedback()
        self._auth(self.owner_token)
        response = self.client.patch(
            f"/api/v1/feedback/feedback/{feedback.id}/",
            {"comment": "Updated comment"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        feedback.refresh_from_db()
        self.assertEqual(feedback.comment, "Updated comment")

    def test_customer_cannot_respond(self) -> None:
        """Customers cannot respond to feedback."""
        feedback = self._create_feedback()
        self._auth(self.customer_token)
        response = self.client.post(
            f"/api/v1/feedback/feedback/{feedback.id}/respond/",
            {"response": "self response"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_rating_validation(self) -> None:
        """Ratings outside 1-5 are rejected."""
        self._auth(self.customer_token)
        response = self.client.post(
            "/api/v1/feedback/feedback/",
            {"rating": 6, "category": "workout"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_tenant_isolation_api(self) -> None:
        """Feedback from another tenant is not visible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_user = make_customer_user(other_tenant, "o@local.test")
        other_feedback = Feedback.objects.create(
            tenant=other_tenant,
            customer=other_user.customer_profile,
            rating=4,
        )
        self._auth(self.owner_token)
        response = self.client.get(f"/api/v1/feedback/feedback/{other_feedback.id}/")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_rejected(self) -> None:
        """Requests without a token are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/feedback/feedback/")
        self.assertEqual(response.status_code, 401)


class FeedbackAnalyticsAPITests(APITestCase):
    """Integration tests for the analytics endpoint."""

    def setUp(self) -> None:
        """Create tenant, owner, and feedback data."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.user1 = make_customer_user(self.tenant, "a@local.test")
        self.user2 = make_customer_user(self.tenant, "b@local.test")
        self.c1 = self.user1.customer_profile
        self.c2 = self.user2.customer_profile
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_analytics_returns_aggregates(self) -> None:
        """Analytics includes rating distribution, categories, sentiment, and trend."""
        Feedback.objects.create(tenant=self.tenant, customer=self.c1, rating=5, category="trainer")
        Feedback.objects.create(tenant=self.tenant, customer=self.c1, rating=5, category="facility")
        Feedback.objects.create(tenant=self.tenant, customer=self.c2, rating=3, category="app")
        Feedback.objects.create(tenant=self.tenant, customer=self.c2, rating=1, category="facility")

        response = self.client.get("/api/v1/feedback/feedback-analytics/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["total_feedback"], 4)
        self.assertEqual(data["average_rating"], 3.5)
        distribution = {d["rating"]: d["count"] for d in data["rating_distribution"]}
        self.assertEqual(distribution[5], 2)
        self.assertEqual(distribution[1], 1)
        self.assertEqual(data["sentiment_summary"]["positive"], 2)
        self.assertEqual(data["sentiment_summary"]["neutral"], 1)
        self.assertEqual(data["sentiment_summary"]["negative"], 1)
        categories = {c["category"]: c["count"] for c in data["category_breakdown"]}
        self.assertEqual(categories["facility"], 2)
        self.assertEqual(len(data["trend"]), 30)

    def test_analytics_empty_tenant(self) -> None:
        """Analytics on an empty tenant returns zeros rather than errors."""
        response = self.client.get("/api/v1/feedback/feedback-analytics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_feedback"], 0)
        self.assertIsNone(response.data["average_rating"])


class FeedbackSurveyAPITests(APITestCase):
    """Integration tests for survey CRUD and submission."""

    def setUp(self) -> None:
        """Create tenant, owner, and customer tokens."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.customer_user = make_customer_user(self.tenant, "cust@local.test")
        self.customer = self.customer_user.customer_profile
        self.customer_token = issue_token(self.customer_user, self.tenant)

    def _auth(self, token) -> None:
        """Set the client auth token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_owner_creates_survey(self) -> None:
        """Owners can create surveys."""
        self._auth(self.owner_token)
        response = self.client.post(
            "/api/v1/feedback/feedback-surveys/",
            {
                "name": "Quarterly Survey",
                "description": "How are we doing?",
                "questions": [
                    {
                        "question_text": "Rate overall",
                        "question_type": "rating",
                        "choices": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Quarterly Survey")
        self.assertEqual(response.data["question_count"], 1)

    def test_customer_submits_survey_response(self) -> None:
        """Customers can submit a response to an active survey."""
        survey = FeedbackSurvey.objects.create(
            tenant=self.tenant,
            name="Check-in",
            questions=[{"question_text": "Rate", "question_type": "rating", "choices": []}],
        )
        self._auth(self.customer_token)
        response = self.client.post(
            f"/api/v1/feedback/feedback-surveys/{survey.id}/submit/",
            {"answers": {"0": 5}},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["survey"], survey.id)
        self.assertEqual(FeedbackResponse.objects.for_tenant(self.tenant).count(), 1)

    def test_customer_cannot_submit_to_inactive_survey(self) -> None:
        """Submissions to inactive surveys are rejected."""
        survey = FeedbackSurvey.objects.create(
            tenant=self.tenant,
            name="Inactive",
            is_active=False,
        )
        self._auth(self.customer_token)
        response = self.client.post(
            f"/api/v1/feedback/feedback-surveys/{survey.id}/submit/",
            {"answers": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_customer_cannot_create_survey(self) -> None:
        """Customers cannot create surveys."""
        self._auth(self.customer_token)
        response = self.client.post(
            "/api/v1/feedback/feedback-surveys/",
            {"name": "Nope", "questions": []},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_responses_list_scoped_to_tenant(self) -> None:
        """Survey responses list is tenant-scoped."""
        survey = FeedbackSurvey.objects.create(tenant=self.tenant, name="S1")
        FeedbackResponse.objects.create(
            tenant=self.tenant, survey=survey, customer=self.customer, answers={}
        )
        self._auth(self.owner_token)
        response = self.client.get("/api/v1/feedback/feedback-responses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)


class FeedbackSerializerTests(TestCase):
    """Tests for the feedback serializers."""

    def setUp(self) -> None:
        """Create tenant, customer, and feedback."""
        self.tenant = provision_tenant(name="Gym", contact_email="owner@local.test")
        self.user = make_customer_user(self.tenant, "s@local.test")
        self.customer = self.user.customer_profile
        self.feedback = Feedback.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            rating=4,
            category=Feedback.Category.DIET,
            comment="Meals could improve.",
        )

    def test_read_serializer_includes_customer_detail(self) -> None:
        """The read serializer nests the customer detail."""
        from apps.feedback.serializers import FeedbackSerializer

        data = FeedbackSerializer(self.feedback).data
        self.assertEqual(data["customer_detail"]["id"], self.customer.id)
        self.assertEqual(data["category"], "diet")
        self.assertEqual(data["rating"], 4)

    def test_write_serializer_rejects_response(self) -> None:
        """Customers cannot set the response fields through the write serializer."""
        from apps.feedback.serializers import FeedbackWriteSerializer

        serializer = FeedbackWriteSerializer(
            data={"rating": 5, "category": "workout", "response": "hacked"}
        )
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("response", serializer.validated_data)
