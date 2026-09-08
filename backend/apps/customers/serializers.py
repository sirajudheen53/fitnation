"""Customer management serializers."""

from django.db import IntegrityError, transaction
from rest_framework import serializers

from PIL import Image

from apps.customers.models import (
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)
from apps.users.models import User

# FBOS-026 part 1: profile photo constraints (JPEG/PNG/WebP, max 5 MB).
ALLOWED_PROFILE_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024


class CustomerSerializer(serializers.ModelSerializer):
    """Serialize customer details.

    Create contract (ADR customer-creation blessing): the payload carries
    ``first_name``/``last_name``/``email`` (+ ``branch``); the linked
    customer-role portal User is auto-provisioned from the email (unusable
    password — customers log in via OTP; ``is_email_verified=True`` since the
    owner vouches for the address). ``name``/``user``/``branch`` remain
    writable for mobile/tests.
    """

    first_name = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=150)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    name = serializers.CharField(max_length=200, required=False)

    class Meta:
        """Serializer metadata."""

        model = Customer
        fields = [
            "id",
            "user",
            "branch",
            "name",
            "first_name",
            "last_name",
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

    def validate_profile_photo(self, value):
        """FBOS-026: accept JPEG/PNG/WebP only, max 5 MB."""
        if not value:
            return value
        if value.size > MAX_PROFILE_PHOTO_BYTES:
            raise serializers.ValidationError("Profile photo must be 5 MB or smaller.")
        fmt = None
        try:
            with Image.open(value) as image:
                fmt = image.format
                image.verify()
        except Exception:
            raise serializers.ValidationError("Profile photo must be a valid JPEG, PNG or WebP image.")
        finally:
            if hasattr(value, "seek"):
                value.seek(0)
        if fmt not in ALLOWED_PROFILE_PHOTO_FORMATS:
            raise serializers.ValidationError("Profile photo must be a JPEG, PNG or WebP image.")
        return value

    def validate(self, data: dict) -> dict:
        """Ensure a tenant does not contain duplicate customer emails.

        Name composition (ADR customer-creation blessing): when either
        ``first_name`` or ``last_name`` is present, the whitespace-collapsed
        ``"{first} {last}".strip()`` composition wins over a provided ``name``.
        """
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
        # Name composition: first/last wins over name when either is present.
        first = (data.get("first_name") or "").strip()
        last = (data.get("last_name") or "").strip()
        if first or last:
            data["name"] = " ".join(f"{first} {last}".split())
        if self.instance is None and not (data.get("name") or "").strip():
            raise serializers.ValidationError(
                {"name": "This field is required."},
            )
        return data

    def create(self, validated_data: dict) -> Customer:
        """Create the customer, auto-provisioning the portal user when absent."""
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        if validated_data.get("user") is None:
            user = self._provision_portal_user(validated_data, validated_data.get("tenant"), first_name, last_name)
            validated_data["user"] = user
        return super().create(validated_data)

    def update(self, instance: Customer, validated_data: dict) -> Customer:
        """Update the customer; write-only name parts never reach the model."""
        validated_data.pop("first_name", None)
        validated_data.pop("last_name", None)
        return super().update(instance, validated_data)

    def _provision_portal_user(self, validated_data, tenant, first_name: str, last_name: str) -> User:
        """Auto-provision the linked customer-role portal account.

        Unusable password (customers authenticate via OTP); the owner vouches
        for the email so the account starts verified. Email conflicts surface
        as a 400 field error — never silently link an existing user.
        """
        try:
            # Nested atomic: a uniqueness violation rolls back to the savepoint
            # so the surrounding request transaction stays usable for the 400.
            with transaction.atomic():
                user = User.objects.create_user(
                    email=validated_data.get("email"),
                    password=None,
                    first_name=first_name,
                    last_name=last_name,
                    role=User.Role.CUSTOMER,
                    tenant=tenant,
                    phone=validated_data.get("phone") or "",
                )
        except IntegrityError:
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."},
            )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return user


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
