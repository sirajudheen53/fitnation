"""AI Coach models — FBOS-017."""
import uuid
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class AIConversation(models.Model):
    class ContextType(models.TextChoices):
        WORKOUT = "workout", "Workout"
        DIET = "diet", "Diet"
        GENERAL = "general", "General"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    tenant_id = models.PositiveIntegerField(db_index=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=200, default="New Conversation")
    context_type = models.CharField(max_length=20, choices=ContextType.choices, default=ContextType.GENERAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["tenant_id", "user"])]


class AIMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AIRecommendation(models.Model):
    class Type(models.TextChoices):
        WORKOUT = "workout", "Workout"
        DIET = "diet", "Diet"
        EXERCISE_TIPS = "exercise_tips", "Exercise Tips"

    tenant_id = models.PositiveIntegerField(db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_recommendations")
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    content = models.JSONField(default=dict)
    is_acted_on = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant_id", "user"])]
