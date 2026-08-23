"""Attendance serializers."""

from rest_framework import serializers

from apps.attendance.models import AttendanceRecord, TrainerAttendance


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """Serialize customer attendance records."""

    class Meta:
        """Serializer metadata."""

        model = AttendanceRecord
        fields = [
            "id",
            "customer",
            "branch",
            "check_in_time",
            "check_out_time",
            "method",
            "date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date", "created_at", "updated_at"]


class TrainerAttendanceSerializer(serializers.ModelSerializer):
    """Serialize trainer attendance records."""

    class Meta:
        """Serializer metadata."""

        model = TrainerAttendance
        fields = [
            "id",
            "trainer",
            "branch",
            "check_in_time",
            "check_out_time",
            "date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date", "created_at", "updated_at"]
