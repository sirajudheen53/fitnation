"""Exercise library serializers."""

from typing import ClassVar

from rest_framework import serializers

from apps.exercises.models import Exercise, ExerciseCategory


class ExerciseCategorySerializer(serializers.ModelSerializer):
    """Serialize exercise category details."""

    exercise_count = serializers.IntegerField(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = ExerciseCategory
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "description",
            "slug",
            "exercise_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "exercise_count", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        """Strip the name and reject duplicates within the tenant."""
        name = value.strip()
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and name:
            queryset = ExerciseCategory.objects.for_tenant(tenant).filter(name__iexact=name)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("A category with this name already exists.")
        return name


class ExerciseSerializer(serializers.ModelSerializer):
    """Serialize exercise details."""

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        """Serializer metadata."""

        model = Exercise
        fields: ClassVar[list[str]] = [
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
        read_only_fields: ClassVar[list[str]] = ["id", "category_name", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        """Strip the name and reject duplicates within the tenant."""
        name = value.strip()
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and name:
            queryset = Exercise.objects.for_tenant(tenant).filter(name__iexact=name)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "An exercise with this name already exists in your library.",
                )
        return name

    def validate_category(self, value: ExerciseCategory) -> ExerciseCategory:
        """Ensure the category belongs to the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The category does not belong to the current tenant.",
            )
        return value
