"""AI Coach serializers."""

from typing import ClassVar

from rest_framework import serializers

from .models import AIConversation, AIMessage, AIRecommendation


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields: ClassVar[list[str]] = ["id", "role", "content", "metadata", "created_at"]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at"]


class AIConversationSerializer(serializers.ModelSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIConversation
        fields: ClassVar[list[str]] = [
            "id",
            "uuid",
            "title",
            "context_type",
            "status",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "uuid", "messages", "created_at", "updated_at"]


class AIRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIRecommendation
        fields: ClassVar[list[str]] = ["id", "type", "content", "is_acted_on", "created_at"]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at"]


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    conversation_id = serializers.IntegerField(required=False)


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    conversation_id = serializers.IntegerField()
    recommendation = serializers.DictField(required=False)
