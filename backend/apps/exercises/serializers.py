"""Exercise library serializers."""

from rest_framework import serializers

from apps.exercises.models import Exercise, ExerciseCategory


class ExerciseCategorySerializer(serializers.ModelSerializer):
    """Serialize exercise category details."""

    exercise_count = serializers.IntegerField(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = ExerciseCategory
        fields = [
            "id",
            "name",
            "description",
            "slug",
            "exercise_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "exercise_count", "created_at", "updated_at"]


class ExerciseSerializer(serializers.ModelSerializer):
    """Serialize exercise details."""

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = Exercise
        fields = [
            "id",
            "name",
            "description",
            "category",
            "category_name",
            "muscle_groups",
            "equipment_needed",
            "difficulty",
            "instructions",
            "media_url",
            "tips",
            "contraindications",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category_name", "created_at", "updated_at"]

    def validate_category(self, value: ExerciseCategory) -> ExerciseCategory:
        """Ensure the category belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The category does not belong to the current tenant.",
            )
        return value
