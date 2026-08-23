"""Vendor onboarding serializers."""

from rest_framework import serializers

from apps.users.models import User
from apps.vendors.models import SubscriptionPlan


class SignupSerializer(serializers.Serializer):
    """Serializer for vendor signup."""

    business_name = serializers.CharField(min_length=2, max_length=200)
    contact_name = serializers.CharField(min_length=2, max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_email(self, value: str) -> str:
        """Ensure the email is not already registered as a gym owner.

        Args:
            value: The submitted email address.

        Returns:
            The validated email.

        Raises:
            serializers.ValidationError: If the email belongs to an existing owner.
        """
        if User.objects.filter(email=value, is_owner=True).exists():
            raise serializers.ValidationError(
                "This email is already registered as a gym owner."
            )
        return value

    def validate_password(self, value: str) -> str:
        """Validate password complexity.

        Args:
            value: The submitted password.

        Returns:
            The validated password.

        Raises:
            serializers.ValidationError: If the password is too weak.
        """
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter."
            )
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError(
                "Password must contain at least one digit."
            )
        return value


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification via query token."""

    token = serializers.UUIDField()


class ResendVerificationSerializer(serializers.Serializer):
    """Serializer for resending verification email."""

    email = serializers.EmailField()


class SelectPlanSerializer(serializers.Serializer):
    """Serializer for selecting a subscription plan."""

    registration_id = serializers.IntegerField()
    plan_code = serializers.ChoiceField(
        choices=[
            ("starter", "Starter"),
            ("professional", "Professional"),
            ("enterprise", "Enterprise"),
        ]
    )


class OnboardingSerializer(serializers.Serializer):
    """Serializer for completing the onboarding wizard."""

    business_type = serializers.ChoiceField(
        choices=[
            ("gym", "Gym"),
            ("yoga_studio", "Yoga Studio"),
            ("crossfit", "Crossfit"),
            ("personal_training", "Personal Training"),
            ("wellness_center", "Wellness Center"),
        ]
    )
    branches_count = serializers.IntegerField(min_value=1, max_value=50)
    primary_branch_name = serializers.CharField(max_length=200)
    primary_branch_address = serializers.CharField(max_length=500)
    primary_branch_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for subscription plan output."""

    class Meta:
        """Serializer metadata."""

        model = SubscriptionPlan
        fields = [
            "id",
            "code",
            "name",
            "price_monthly",
            "price_yearly",
            "max_branches",
            "max_customers",
            "max_trainers",
            "features",
            "is_active",
            "sort_order",
        ]
