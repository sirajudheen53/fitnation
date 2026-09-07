"""Attendance serializers."""

from rest_framework import serializers

from apps.attendance.models import (
    AttendanceRecord,
    StaffAttendance,
    TrainerAttendance,
)


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """Serialize customer attendance records.

    Exposes the ``person_*`` shape the frontend expects (``person_id``,
    ``person_name``, ``person_type``, ``branch_id``, ``branch_name`` and a
    derived ``status``) while keeping the raw ``customer``/``branch`` FK
    fields for backward compatibility.
    """

    person_id = serializers.IntegerField(source="customer_id", read_only=True)
    person_name = serializers.CharField(source="customer.name", read_only=True)
    person_type = serializers.SerializerMethodField()
    branch_id = serializers.IntegerField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = AttendanceRecord
        fields = [
            "id",
            "customer",
            "person_id",
            "person_name",
            "person_type",
            "branch",
            "branch_id",
            "branch_name",
            "check_in_time",
            "check_out_time",
            "status",
            "method",
            "date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date", "created_at", "updated_at"]

    def get_person_type(self, obj: AttendanceRecord) -> str:
        """Return the attendance person type."""
        return "customer"


class TrainerAttendanceSerializer(serializers.ModelSerializer):
    """Serialize trainer attendance records.

    Mirrors the customer ``person_*`` shape with ``person_type`` fixed to
    ``"trainer"`` and the trainer's display name resolved from the linked
    user account.
    """

    person_id = serializers.IntegerField(source="trainer_id", read_only=True)
    person_name = serializers.SerializerMethodField()
    person_type = serializers.SerializerMethodField()
    branch_id = serializers.IntegerField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = TrainerAttendance
        fields = [
            "id",
            "trainer",
            "person_id",
            "person_name",
            "person_type",
            "branch",
            "branch_id",
            "branch_name",
            "check_in_time",
            "check_out_time",
            "status",
            "date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date", "created_at", "updated_at"]

    def get_person_name(self, obj: TrainerAttendance) -> str:
        """Return the trainer's display name from the linked user."""
        full_name = f"{obj.trainer.user.first_name} {obj.trainer.user.last_name}"
        return full_name.strip() or obj.trainer.user.email

    def get_person_type(self, obj: TrainerAttendance) -> str:
        """Return the attendance person type."""
        return "trainer"


class CheckInSerializer(serializers.Serializer):
    """Validate a walk-in check-in request payload."""

    person_id = serializers.IntegerField(min_value=1)
    person_type = serializers.ChoiceField(choices=["customer", "trainer", "staff"])
    branch_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )
    status = serializers.ChoiceField(
        choices=["present", "late", "absent", "left"],
        required=False,
    )


class StaffAttendanceSerializer(serializers.ModelSerializer):
    """Serialize staff attendance records.

    Mirrors the customer ``person_*`` shape with ``person_type`` fixed to
    ``"staff"`` and the staff member's display name resolved from the
    linked user account.
    """

    person_id = serializers.IntegerField(source="user_id", read_only=True)
    person_name = serializers.SerializerMethodField()
    person_type = serializers.SerializerMethodField()
    branch_id = serializers.IntegerField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = StaffAttendance
        fields = [
            "id",
            "user",
            "person_id",
            "person_name",
            "person_type",
            "branch",
            "branch_id",
            "branch_name",
            "check_in_time",
            "check_out_time",
            "status",
            "method",
            "date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date", "created_at", "updated_at"]

    def get_person_name(self, obj: StaffAttendance) -> str:
        """Return the staff member's display name from the linked user."""
        full_name = obj.user.get_full_name().strip()
        return full_name or obj.user.email

    def get_person_type(self, obj: StaffAttendance) -> str:
        """Return the attendance person type."""
        return "staff"
