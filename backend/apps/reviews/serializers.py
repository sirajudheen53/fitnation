"""Serializers for the reviews app (FBOS-034)."""

from rest_framework import serializers

from apps.customers.serializers import CustomerSerializer
from apps.reviews.models import Review, ReviewResponse


class ReviewResponseSerializer(serializers.ModelSerializer):
    """Serialize a staff response to a review."""

    author_name = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = ReviewResponse
        fields = [
            "id",
            "review",
            "text",
            "author",
            "author_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "review",
            "author",
            "author_name",
            "created_at",
            "updated_at",
        ]

    def get_author_name(self, obj: ReviewResponse) -> str | None:
        """Return the author's display name."""
        if obj.author_id is None:
            return None
        return obj.author.get_full_name() or obj.author.email


class ReviewSerializer(serializers.ModelSerializer):
    """Serialize a review with nested customer and response details."""

    customer_detail = CustomerSerializer(source="customer", read_only=True)
    response = ReviewResponseSerializer(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Review
        fields = [
            "id",
            "customer",
            "customer_detail",
            "branch",
            "rating",
            "text",
            "response",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer",
            "customer_detail",
            "response",
            "created_at",
            "updated_at",
        ]

    def validate_rating(self, value: int) -> int:
        """Enforce a 1-5 rating range at the API layer."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class ReviewWriteSerializer(serializers.ModelSerializer):
    """Serializer used when customers submit a new review."""

    class Meta:
        """Serializer metadata."""

        model = Review
        fields = [
            "id",
            "customer",
            "branch",
            "rating",
            "text",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "customer", "created_at", "updated_at"]
        extra_kwargs = {"customer": {"required": False}}

    def validate_rating(self, value: int) -> int:
        """Enforce a 1-5 rating range."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
