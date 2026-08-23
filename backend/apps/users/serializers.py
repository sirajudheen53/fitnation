"""User serializers."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.auth import AuthToken
from apps.users.models import User


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
            raise serializers.ValidationError(
                "Managers cannot create owners or other managers."
            )
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
            raise serializers.ValidationError(
                "Managers cannot change users to owner or manager."
            )
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
