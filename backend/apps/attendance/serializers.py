"""Attendance serializers."""

from typing import ClassVar

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

    Issue #83: a record still open past check-in + 2h is rendered with
    the derived auto check-out (``check_out_time`` = check-in + 2h,
    ``check_out_is_auto`` = true) so the UI never shows a zombie open
    visit — without writing the guess to the DB. A stored check-out
    (real punch or admin edit) always renders as-is with the flag false.
    """

    person_id = serializers.IntegerField(source="customer_id", read_only=True)
    person_name = serializers.CharField(source="customer.name", read_only=True)
    person_type = serializers.SerializerMethodField()
    # Issue #81: the punch's member was deleted — name renders "Deleted user"
    # (scrubbed row); the flag lets the UI badge the row.
    person_is_deleted = serializers.SerializerMethodField()
    branch_id = serializers.IntegerField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = AttendanceRecord
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "person_id",
            "person_name",
            "person_type",
            "person_is_deleted",
            "branch",
            "branch_id",
            "branch_name",
            "check_in_time",
            "check_out_time",
            "check_out_is_auto",
            "status",
            "method",
            "date",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "date",
            "check_out_is_auto",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance: AttendanceRecord) -> dict:
        """Render the derived auto check-out for open records past +2h."""
        rep = super().to_representation(instance)
        derived = instance.auto_check_out_time
        if derived is not None:
            rep["check_out_time"] = serializers.DateTimeField().to_representation(derived)
            rep["check_out_is_auto"] = True
        else:
            rep["check_out_is_auto"] = bool(instance.check_out_time is not None and instance.check_out_is_auto)
        return rep

    def get_person_type(self, obj: AttendanceRecord) -> str:
        """Return the attendance person type."""
        return "customer"

    def get_person_is_deleted(self, obj: AttendanceRecord) -> bool:
        """Return the soft-delete marker of the punched member (issue #81)."""
        return obj.customer.deleted_at is not None


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
        fields: ClassVar[list[str]] = [
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
        read_only_fields: ClassVar[list[str]] = ["id", "date", "created_at", "updated_at"]

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
        fields: ClassVar[list[str]] = [
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
        read_only_fields: ClassVar[list[str]] = ["id", "date", "created_at", "updated_at"]

    def get_person_name(self, obj: StaffAttendance) -> str:
        """Return the staff member's display name from the linked user."""
        full_name = obj.user.get_full_name().strip()
        return full_name or obj.user.email

    def get_person_type(self, obj: StaffAttendance) -> str:
        """Return the attendance person type."""
        return "staff"
