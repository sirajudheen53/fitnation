"""User serializers."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.auth import AuthToken
from apps.users.models import Trainer, TrainerCustomerAssignment, TrainerSchedule, User


class UserSerializer(serializers.ModelSerializer):
    """Serialize user details."""

    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "is_owner",
            "is_active",
            "is_staff",
            "is_email_verified",
            "tenant_id",
            "tenant_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new user."""

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        validators=[validate_password],
    )
    branch_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        """Serializer metadata."""

        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "password",
            "branch_id",
        ]

    def validate_role(self, value: str) -> str:
        """Validate that a manager cannot create owners/managers above their rank.

        Args:
            value: The requested role string.

        Returns:
            The validated role string.

        Raises:
            serializers.ValidationError: If the role is disallowed for the actor.
        """
        request = self.context["request"]
        if request.user.role == User.Role.MANAGER and value in {
            User.Role.GYM_OWNER,
            User.Role.MANAGER,
        }:
            raise serializers.ValidationError("Managers cannot create owners or other managers.")
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating an existing user."""

    class Meta:
        """Serializer metadata."""

        model = User
        fields = ["first_name", "last_name", "phone", "role", "is_active"]

    def validate_role(self, value: str) -> str:
        """Validate role updates do not escalate privileges.

        Args:
            value: The requested role string.

        Returns:
            The validated role string.

        Raises:
            serializers.ValidationError: If a manager attempts an unauthorized role.
        """
        request = self.context["request"]
        instance = self.instance
        if (
            request.user.role == User.Role.MANAGER
            and instance
            and instance.role != value
            and value in {User.Role.GYM_OWNER, User.Role.MANAGER}
        ):
            raise serializers.ValidationError("Managers cannot change users to owner or manager.")
        return value


class LoginSerializer(serializers.Serializer):
    """Serializer for email/password login."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    device_type = serializers.ChoiceField(
        choices=AuthToken.DeviceType.choices,
        required=False,
        allow_blank=True,
    )


class OTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP request."""

    phone = serializers.CharField(max_length=20)


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification."""

    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6)
    device_type = serializers.ChoiceField(
        choices=AuthToken.DeviceType.choices,
        required=False,
        allow_blank=True,
    )


# ── Trainer serializers ────────────────────────────────────────────────────────


class TrainerScheduleSerializer(serializers.ModelSerializer):
    """Serializer for TrainerSchedule model."""

    class Meta:
        """Serializer metadata."""

        model = TrainerSchedule
        fields = [
            "id",
            "trainer",
            "day_of_week",
            "start_time",
            "end_time",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "trainer"]

    def to_internal_value(self, data: dict) -> dict:
        """Ensure is_available defaults to True when not provided."""
        if "is_available" not in data:
            data = data.copy()
            data["is_available"] = True
        return super().to_internal_value(data)


class TrainerSerializer(serializers.ModelSerializer):
    """Serializer for Trainer model with nested user info."""

    email = serializers.CharField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    schedules = TrainerScheduleSerializer(many=True, read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Trainer
        fields = [
            "id",
            "user_id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "specialization",
            "bio",
            "is_active",
            "certifications",
            "experience_years",
            "rating",
            "profile_photo",
            "max_clients",
            "schedules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "rating"]


class TrainerCreateSerializer(serializers.Serializer):
    """Serializer for creating a new trainer (creates user + profile)."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        validators=[validate_password],
    )
    specialization = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    certifications = serializers.JSONField(required=False, default=list)
    experience_years = serializers.IntegerField(required=False, default=0)
    max_clients = serializers.IntegerField(required=False, default=50)
    profile_photo = serializers.URLField(required=False, allow_blank=True)

    def to_internal_value(self, data: dict) -> dict:
        """Parse certifications from JSON string if needed."""
        certifications = data.get("certifications")
        if isinstance(certifications, str):
            import json

            try:
                data = data.copy()
                data["certifications"] = json.loads(certifications)
            except (json.JSONDecodeError, ValueError):
                raise serializers.ValidationError({"certifications": "Value must be valid JSON."})
        return super().to_internal_value(data)


class TrainerUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating an existing trainer profile."""

    class Meta:
        """Serializer metadata."""

        model = Trainer
        fields = [
            "specialization",
            "bio",
            "is_active",
            "certifications",
            "experience_years",
            "profile_photo",
            "max_clients",
        ]


class TrainerCustomerAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for TrainerCustomerAssignment model."""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerCustomerAssignment
        fields = [
            "id",
            "trainer",
            "customer",
            "is_active",
            "assigned_at",
            "unassigned_at",
            "customer_name",
            "customer_email",
            "trainer_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assigned_at",
            "unassigned_at",
            "created_at",
            "updated_at",
        ]


class TrainerMetricsSerializer(serializers.Serializer):
    """Serializer for trainer performance metrics response."""

    trainer_id = serializers.IntegerField()
    active_clients = serializers.IntegerField()
    rating = serializers.FloatField()
    max_clients = serializers.IntegerField()
    utilization = serializers.FloatField()
    total_assignments = serializers.IntegerField()
