"""Trainer management serializers (FBOS-007)."""

from rest_framework import serializers

from apps.trainers.models import TrainerAssignment, TrainerPerformance
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "rating"]


class TrainerAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for the branch-scoped trainer↔customer assignment."""

    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerAssignment
        fields = [
            "id",
            "trainer",
            "customer",
            "branch",
            "assigned_at",
            "unassigned_at",
            "is_active",
            "trainer_email",
            "customer_name",
            "branch_name",
        ]
        read_only_fields = ["id", "assigned_at", "unassigned_at"]


class TrainerPerformanceSerializer(serializers.ModelSerializer):
    """Serializer for monthly trainer performance snapshots."""

    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerPerformance
        fields = [
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
        read_only_fields = ["id", "created_at", "updated_at"]


class TrainerScheduleSerializer(serializers.ModelSerializer):
    """Serializer for the existing users.TrainerSchedule model."""

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
        read_only_fields = ["id", "created_at", "updated_at"]
