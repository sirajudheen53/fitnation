"""Trainer management serializers (FBOS-007, issue #52)."""

from typing import ClassVar

from rest_framework import serializers

from apps.customers.serializers import DeletedCustomerFlagMixin
from apps.trainers.models import TrainerAssignment, TrainerPerformance, TrainerSession
from apps.users.models import Trainer, TrainerSchedule
from apps.users.phone import normalize_e164
from apps.users.serializers import reject_registered_phone
from apps.users.trainer_services import update_trainer


class TrainerSerializer(serializers.ModelSerializer):
    """Serializer for the users.Trainer profile model.

    ``phone`` (issue #97) is writable through the linked user: payloads are
    normalized to E.164 (#88) and rejected with ``phone_already_registered``
    when another tenant account holds the number — the ADR-002 customers
    conflict rule, applied to profile edits (:func:`reject_registered_phone`).
    The write routes through :func:`update_trainer` so an actual number
    change also purges outstanding OTP codes for the freed old phone
    (#72 hygiene), same as the ``/users/trainers/`` PATCH path.
    """

    email = serializers.CharField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True, max_length=20)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Trainer
        fields: ClassVar[list[str]] = [
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
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at", "rating"]

    def validate_phone(self, value: str) -> str:
        """Canonicalize the phone to E.164 (#88)."""
        return normalize_e164(value)

    def validate(self, data: dict) -> dict:
        """ADR-002 conflict check when the payload carries a phone (#97)."""
        phone = (data.get("user") or {}).get("phone")
        if phone is not None:
            request = self.context.get("request")
            tenant = getattr(request, "tenant", None) if request else None
            exclude_user = self.instance.user if self.instance is not None else None
            reject_registered_phone(tenant, phone, exclude_user=exclude_user)
        return data

    def update(self, instance: Trainer, validated_data: dict) -> Trainer:
        """Persist profile fields; the dotted-source phone lands on the user.

        DRF nests ``source="user.phone"`` payload under ``validated_data
        ["user"]``, which ``ModelSerializer.update`` cannot apply itself —
        the phone routes through :func:`update_trainer` (E.164 write + OTP
        purge) while the rest take the normal model path.
        """
        user_updates = validated_data.pop("user", {})
        phone = user_updates.get("phone")
        if phone is not None:
            return update_trainer(instance, phone=phone, **validated_data)
        return super().update(instance, validated_data)


class TrainerAssignmentSerializer(DeletedCustomerFlagMixin, serializers.ModelSerializer):
    """Serializer for the branch-scoped trainer↔customer assignment."""

    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerAssignment
        fields: ClassVar[list[str]] = [
            "id",
            "trainer",
            "customer",
            "branch",
            "assigned_at",
            "unassigned_at",
            "is_active",
            "trainer_email",
            "customer_name",
            "customer_is_deleted",
            "branch_name",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "assigned_at", "unassigned_at"]


class TrainerPerformanceSerializer(serializers.ModelSerializer):
    """Serializer for monthly trainer performance snapshots."""

    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerPerformance
        fields: ClassVar[list[str]] = [
            "id",
            "trainer",
            "month",
            "revenue",
            "customer_count",
            "rating_avg",
            "sessions_completed",
            "trainer_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]


class TrainerScheduleSerializer(serializers.ModelSerializer):
    """Serializer for the existing users.TrainerSchedule model."""

    class Meta:
        """Serializer metadata."""

        model = TrainerSchedule
        fields: ClassVar[list[str]] = [
            "id",
            "trainer",
            "day_of_week",
            "start_time",
            "end_time",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]


class TrainerSessionSerializer(DeletedCustomerFlagMixin, serializers.ModelSerializer):
    """Serializer for PT sessions.

    ``status`` is read-only — lifecycle moves happen through the
    ``complete`` / ``no-show`` / ``cancel`` actions. Entitlement and overlap
    gates run in ``apps.trainers.services`` (409 with a machine-readable
    ``reason``), not here. ``customer_is_deleted`` (issue #81) badges a
    session whose member was deleted; the name renders "Deleted user".
    """

    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerSession
        fields: ClassVar[list[str]] = [
            "id",
            "trainer",
            "customer",
            "branch",
            "scheduled_at",
            "duration_minutes",
            "status",
            "notes",
            "trainer_email",
            "customer_name",
            "customer_is_deleted",
            "branch_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "status", "created_at", "updated_at"]

    def validate_trainer(self, value: Trainer) -> Trainer:
        """Ensure the trainer belongs to the request's tenant."""
        tenant = self.context["request"].tenant
        if value.user.tenant_id != tenant.id:
            raise serializers.ValidationError("Trainer does not belong to this tenant.")
        return value

    def validate_customer(self, value) -> object:
        """Ensure the customer belongs to the request's tenant."""
        tenant = self.context["request"].tenant
        if value.tenant_id != tenant.id:
            raise serializers.ValidationError("Customer does not belong to this tenant.")
        return value

    def validate_branch(self, value) -> object:
        """Ensure the branch belongs to the request's tenant."""
        tenant = self.context["request"].tenant
        if value is not None and value.tenant_id != tenant.id:
            raise serializers.ValidationError("Branch does not belong to this tenant.")
        return value
