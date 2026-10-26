"""Trainer management serializers (FBOS-007, issue #52)."""

from typing import ClassVar

from rest_framework import serializers

from apps.customers.serializers import DeletedCustomerFlagMixin
from apps.trainers.models import TrainerAssignment, TrainerPerformance, TrainerSession
from apps.users.models import Trainer, TrainerSchedule


class TrainerSerializer(serializers.ModelSerializer):
    """Serializer for the users.Trainer profile model."""

    email = serializers.CharField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
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
