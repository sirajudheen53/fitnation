"""Tests for the AI Coach app: models, services, APIs, permissions, isolation."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.ai_coach.models import AIConversation, AIMessage, AIRecommendation
from apps.ai_coach.services.ai_service import build_user_context, generate_response
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


def _make_tenant_and_owner(email: str = "owner@coach.test"):
    """Provision a tenant and owner user, returning both."""
    tenant = provision_tenant(name="Iron Peak", contact_email=email)
    owner = create_owner_user(
        tenant=tenant,
        email=email,
        password_hash="pbkdf2_sha256$hashed",
        contact_name="Owner User",
    )
    return tenant, owner


class AICoachModelTests(TestCase):
    """Unit tests for AI Coach models."""

    def setUp(self) -> None:
        """Create tenant and owner."""
        self.tenant, self.owner = _make_tenant_and_owner()

    def _customer(self, email: str) -> User:
        """Create a customer user in the tenant."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Test",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_conversation_creation(self) -> None:
        """AIConversation can be created with defaults."""
        conv = AIConversation.objects.create(tenant_id=self.tenant.id, user=self.owner)
        self.assertEqual(conv.title, "New Conversation")
        self.assertEqual(conv.context_type, AIConversation.ContextType.GENERAL)
        self.assertEqual(conv.status, AIConversation.Status.ACTIVE)
        self.assertIsNotNone(conv.uuid)

    def test_conversation_uuid_unique(self) -> None:
        """Each conversation gets a unique UUID."""
        c1 = AIConversation.objects.create(tenant_id=self.tenant.id, user=self.owner)
        c2 = AIConversation.objects.create(tenant_id=self.tenant.id, user=self.owner)
        self.assertNotEqual(c1.uuid, c2.uuid)

    def test_message_ordering(self) -> None:
        """Messages are ordered by creation time ascending."""
        conv = AIConversation.objects.create(tenant_id=self.tenant.id, user=self.owner)
        m1 = AIMessage.objects.create(conversation=conv, role="user", content="first")
        m2 = AIMessage.objects.create(conversation=conv, role="assistant", content="second")
        self.assertEqual(list(conv.messages.all()), [m1, m2])

    def test_recommendation_creation(self) -> None:
        """AIRecommendation stores JSON content and type."""
        conv = AIConversation.objects.create(tenant_id=self.tenant.id, user=self.owner)
        rec = AIRecommendation.objects.create(
            tenant_id=self.tenant.id,
            user=self.owner,
            conversation=conv,
            type=AIRecommendation.Type.WORKOUT,
            content={"suggestion": "Try squats"},
        )
        self.assertFalse(rec.is_acted_on)
        self.assertEqual(rec.type, AIRecommendation.Type.WORKOUT)

    def test_conversation_cascade_delete_messages(self) -> None:
        """Deleting a conversation deletes its messages."""
        conv = AIConversation.objects.create(tenant_id=self.tenant.id, user=self.owner)
        AIMessage.objects.create(conversation=conv, role="user", content="hi")
        conv_id = conv.id
        conv.delete()
        self.assertEqual(AIMessage.objects.filter(conversation_id=conv_id).count(), 0)


class AIServiceTests(TestCase):
    """Tests for the AI service logic."""

    def setUp(self) -> None:
        """Create tenant and owner."""
        self.tenant, self.owner = _make_tenant_and_owner()

    def test_build_user_context(self) -> None:
        """Context is built with user name and empty data lists."""
        ctx = build_user_context(self.owner)
        self.assertEqual(ctx["name"], "Owner User")
        self.assertIn("workouts", ctx)
        self.assertIn("diet_plans", ctx)
        self.assertIn("goals", ctx)

    def test_generate_response_general(self) -> None:
        """A general message returns the intro response with no recommendation."""
        response, recommendation = generate_response("hello", self.owner)
        self.assertIn("AI fitness coach", response)
        self.assertIsNone(recommendation)

    def test_generate_response_workout(self) -> None:
        """A workout message returns a workout recommendation."""
        response, rec = generate_response("give me a workout plan", self.owner)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["type"], "workout")
        self.assertIn("suggestion", rec["content"])

    def test_generate_response_diet(self) -> None:
        """A diet message returns a diet recommendation."""
        response, rec = generate_response("diet advice please", self.owner)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["type"], "diet")

    def test_generate_response_form(self) -> None:
        """A form/technique message returns exercise tips."""
        response, rec = generate_response("what about form", self.owner)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["type"], "exercise_tips")


class AICoachAPIBase(APITestCase):
    """Shared setup for API tests."""

    def setUp(self) -> None:
        """Create tenant, owner, token, and a conversation."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.conversation = AIConversation.objects.create(
            tenant_id=self.tenant.id, user=self.owner, title="Test Chat"
        )


class AICoachAPITests(AICoachAPIBase):
    """API endpoint tests."""

    def test_list_conversations(self) -> None:
        """Authenticated user can list their conversations."""
        response = self.client.get("/api/v1/ai/coach/conversations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_chat_creates_conversation_and_messages(self) -> None:
        """Chat without conversation_id creates a conversation and messages."""
        response = self.client.post(
            "/api/v1/ai/coach/chat/", {"message": "hello coach"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        conv_id = response.data["conversation_id"]
        conv = AIConversation.objects.get(id=conv_id)
        self.assertEqual(conv.messages.filter(role="user").count(), 1)
        self.assertEqual(conv.messages.filter(role="assistant").count(), 1)
        self.assertIsNone(response.data["recommendation"])

    def test_chat_returns_recommendation_for_workout(self) -> None:
        """Chat with a workout keyword returns a recommendation."""
        response = self.client.post(
            "/api/v1/ai/coach/chat/", {"message": "recommend a workout"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["recommendation"])
        self.assertEqual(response.data["recommendation"]["type"], "workout")

    def test_chat_reuses_existing_conversation(self) -> None:
        """Chat with a conversation_id reuses that conversation."""
        response = self.client.post(
            "/api/v1/ai/coach/chat/",
            {"message": "hello", "conversation_id": self.conversation.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["conversation_id"], self.conversation.id)
        self.assertEqual(self.conversation.messages.filter(role="assistant").count(), 1)

    def test_chat_requires_auth(self) -> None:
        """Unauthenticated requests are rejected."""
        self.client.credentials()
        response = self.client.post(
            "/api/v1/ai/coach/chat/", {"message": "hi"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_chat_requires_valid_message(self) -> None:
        """Missing message returns 400."""
        response = self.client.post("/api/v1/ai/coach/chat/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_conversation_messages_endpoint(self) -> None:
        """Messages endpoint returns messages for a conversation."""
        AIMessage.objects.create(conversation=self.conversation, role="user", content="hello")
        response = self.client.get(
            f"/api/v1/ai/coach/conversations/{self.conversation.id}/messages/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["role"], "user")

    def test_conversation_messages_requires_auth(self) -> None:
        """Unauthenticated message fetch is rejected."""
        self.client.credentials()
        response = self.client.get(
            f"/api/v1/ai/coach/conversations/{self.conversation.id}/messages/"
        )
        self.assertEqual(response.status_code, 401)

    def test_list_recommendations(self) -> None:
        """Authenticated user can list recommendations."""
        AIRecommendation.objects.create(
            tenant_id=self.tenant.id,
            user=self.owner,
            conversation=self.conversation,
            type=AIRecommendation.Type.WORKOUT,
            content={"suggestion": "Squats"},
        )
        response = self.client.get("/api/v1/ai/coach/recommendations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_patch_recommendation_acted_on(self) -> None:
        """Recommendation can be marked as acted on via PATCH."""
        rec = AIRecommendation.objects.create(
            tenant_id=self.tenant.id,
            user=self.owner,
            conversation=self.conversation,
            type=AIRecommendation.Type.DIET,
            content={"suggestion": "Eat protein"},
        )
        response = self.client.patch(
            f"/api/v1/ai/coach/recommendations/{rec.id}/",
            {"is_acted_on": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        rec.refresh_from_db()
        self.assertTrue(rec.is_acted_on)


class AICoachIsolationTests(AICoachAPIBase):
    """Cross-tenant and cross-user isolation tests."""

    def test_tenant_isolation(self) -> None:
        """Users cannot see another tenant's conversations."""
        other_tenant, _ = _make_tenant_and_owner(email="other@coach.test")
        AIConversation.objects.create(tenant_id=other_tenant.id, user=self.owner)
        response = self.client.get("/api/v1/ai/coach/conversations/")
        self.assertEqual(response.status_code, 200)
        # Only the owner's own conversation in this tenant is visible.
        self.assertEqual(len(response.data["results"]), 1)

    def test_cannot_access_other_users_conversation(self) -> None:
        """A user cannot fetch messages of another user's conversation."""
        other_user = User.objects.create_user(
            email="otheruser@coach.test",
            password="F1tNati0n!",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        foreign_conv = AIConversation.objects.create(
            tenant_id=self.tenant.id, user=other_user
        )
        response = self.client.get(
            f"/api/v1/ai/coach/conversations/{foreign_conv.id}/messages/"
        )
        self.assertEqual(response.status_code, 404)
