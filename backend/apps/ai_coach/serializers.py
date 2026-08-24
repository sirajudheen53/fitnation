"""AI Coach serializers."""
from rest_framework import serializers
from .models import AIConversation, AIMessage, AIRecommendation


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ["id", "role", "content", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


class AIConversationSerializer(serializers.ModelSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIConversation
        fields = ["id", "uuid", "title", "context_type", "status", "messages", "created_at", "updated_at"]
        read_only_fields = ["id", "uuid", "messages", "created_at", "updated_at"]


class AIRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIRecommendation
        fields = ["id", "type", "content", "is_acted_on", "created_at"]
        read_only_fields = ["id", "created_at"]


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    conversation_id = serializers.IntegerField(required=False)


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    conversation_id = serializers.IntegerField()
    recommendation = serializers.DictField(required=False)
