"""Customer management serializers."""

from rest_framework import serializers

from apps.customers.models import (
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)


class CustomerSerializer(serializers.ModelSerializer):
    """Serialize customer details."""

    class Meta:
        """Serializer metadata."""

        model = Customer
        fields = [
            "id",
            "user",
            "branch",
            "name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address_street",
            "address_city",
            "address_state",
            "address_postal_code",
            "profile_photo",
            "status",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data: dict) -> dict:
        """Ensure a tenant does not contain duplicate customer emails."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        email = data.get("email")
        if tenant and email:
            queryset = Customer.objects.filter(tenant=tenant, email=email)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"email": "A customer with this email already exists."},
                )
        return data


class HealthProfileSerializer(serializers.ModelSerializer):
    """Serialize health profile details."""

    class Meta:
        """Serializer metadata."""

        model = HealthProfile
        fields = [
            "id",
            "customer",
            "height_cm",
            "weight_kg",
            "bmi",
            "blood_group",
            "injuries",
            "current_injuries",
            "past_injuries",
            "medical_info",
            "medical_conditions",
            "allergies",
            "food_allergies",
            "medications",
            "dietary_restrictions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "bmi", "created_at", "updated_at"]


class FitnessGoalSerializer(serializers.ModelSerializer):
    """Serialize fitness goal details."""

    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = FitnessGoal
        fields = [
            "id",
            "customer",
            "goal_type",
            "is_active",
            "status",
            "target_value",
            "target_unit",
            "target_date",
            "current_value",
            "progress_percentage",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_progress_percentage(self, obj: FitnessGoal) -> float | None:
        """Return the computed goal progress percentage."""
        return obj.progress_percentage


class BodyMeasurementSerializer(serializers.ModelSerializer):
    """Serialize body measurement details."""

    class Meta:
        """Serializer metadata."""

        model = BodyMeasurement
        fields = [
            "id",
            "customer",
            "date_logged",
            "weight_kg",
            "height_cm",
            "bmi",
            "body_fat_percentage",
            "chest_cm",
            "waist_cm",
            "hips_cm",
            "biceps_cm",
            "thighs_cm",
            "neck_cm",
            "arms_cm",
            "legs_cm",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "bmi", "date_logged", "created_at", "updated_at"]


class ProgressPhotoSerializer(serializers.ModelSerializer):
    """Serialize progress photo details."""

    class Meta:
        """Serializer metadata."""

        model = ProgressPhoto
        fields = [
            "id",
            "customer",
            "image",
            "caption",
            "taken_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "customer", "taken_at", "created_at", "updated_at"]
