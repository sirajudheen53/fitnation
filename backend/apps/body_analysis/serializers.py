"""Body analysis serializers."""

from rest_framework import serializers

from apps.body_analysis.models import BodyAnalysis, BodyPhoto, BodyProgressLog


class BodyAnalysisSerializer(serializers.ModelSerializer):
    """Serialize body analysis details."""

    photos = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = BodyAnalysis
        fields = [
            "id",
            "uuid",
            "user",
            "analysis_date",
            "height_cm",
            "weight_kg",
            "bmi",
            "body_fat_pct",
            "muscle_mass_pct",
            "posture_score",
            "notes",
            "photo_count",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "bmi", "photo_count", "created_at", "updated_at"]


class BodyPhotoSerializer(serializers.ModelSerializer):
    """Serialize body photo details."""

    class Meta:
        model = BodyPhoto
        fields = [
            "id",
            "analysis",
            "photo_type",
            "image_url",
            "uploaded_at",
            "is_processed",
            "analysis_result",
        ]
        read_only_fields = ["id", "uploaded_at"]


class BodyPhotoUploadSerializer(serializers.Serializer):
    """Validate multipart body-photo upload payload."""

    analysis_id = serializers.IntegerField()
    photo_type = serializers.ChoiceField(
        choices=BodyPhoto.PhotoType.choices,
        default=BodyPhoto.PhotoType.FRONT,
    )
    image_url = serializers.URLField(allow_blank=True)


class BodyProgressLogSerializer(serializers.ModelSerializer):
    """Serialize a body progress log entry."""

    class Meta:
        model = BodyProgressLog
        fields = [
            "id",
            "user",
            "date",
            "metric_type",
            "value",
            "unit",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BodyProgressTrendSerializer(serializers.Serializer):
    """Serialize aggregated trend data for charting.

    Each point pairs a date with a metric value, ordered chronologically.
    """

    date = serializers.DateField()
    value = serializers.FloatField()
