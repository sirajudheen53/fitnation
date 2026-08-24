"""Serializers for the feedback app (FBOS-015)."""

from rest_framework import serializers

from apps.customers.serializers import CustomerSerializer
from apps.feedback.models import Feedback, FeedbackResponse, FeedbackSurvey


class FeedbackSerializer(serializers.ModelSerializer):
    """Serialize feedback with nested customer and responder details."""

    customer_detail = CustomerSerializer(source="customer", read_only=True)
    response_by_name = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = Feedback
        fields = [
            "id",
            "customer",
            "customer_detail",
            "rating",
            "category",
            "comment",
            "is_anonymous",
            "response",
            "response_by",
            "response_by_name",
            "response_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer_detail",
            "response_by",
            "response_by_name",
            "response_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "customer": {"required": False, "allow_null": True},
            "response": {"required": False},
        }

    def get_response_by_name(self, obj: Feedback) -> str | None:
        """Return the responder's display name."""
        if obj.response_by_id is None:
            return None
        return obj.response_by.get_full_name() or obj.response_by.email

    def validate_rating(self, value: int) -> int:
        """Enforce a 1-5 rating range at the API layer."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class FeedbackWriteSerializer(serializers.ModelSerializer):
    """Serializer used when customers submit new feedback."""

    class Meta:
        model = Feedback
        fields = [
            "id",
            "customer",
            "rating",
            "category",
            "comment",
            "is_anonymous",
            "response",
            "response_by",
            "response_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "response",
            "response_by",
            "response_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"customer": {"required": False}}

    def validate_rating(self, value: int) -> int:
        """Enforce a 1-5 rating range."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class FeedbackResponseSerializer(serializers.ModelSerializer):
    """Serializer for a trainer/owner responding to feedback."""

    class Meta:
        model = Feedback
        fields = ["id", "response", "response_by", "response_at"]
        read_only_fields = ["id", "response_by", "response_at"]


class FeedbackSurveySerializer(serializers.ModelSerializer):
    """Serialize a feedback survey."""

    question_count = serializers.SerializerMethodField()

    class Meta:
        model = FeedbackSurvey
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "questions",
            "question_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "question_count", "created_at", "updated_at"]

    def get_question_count(self, obj: FeedbackSurvey) -> int:
        """Return the number of questions in the survey."""
        return len(obj.questions or [])


class FeedbackSurveyResponseSerializer(serializers.ModelSerializer):
    """Serialize a submitted survey response with nested survey/customer context."""

    survey_name = serializers.CharField(source="survey.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = FeedbackResponse
        fields = [
            "id",
            "survey",
            "survey_name",
            "customer",
            "customer_name",
            "answers",
            "submitted_at",
        ]
        read_only_fields = ["id", "survey_name", "customer_name", "submitted_at"]
        extra_kwargs = {"customer": {"required": False}}
