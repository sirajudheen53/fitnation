"""Attendance business logic services."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.attendance.models import AttendanceRecord, TrainerAttendance
from apps.customers.models import Customer
from apps.users.models import Trainer


def log_check_in(
    *,
    tenant,
    person_id: int,
    person_type: str,
    branch_id: int | None = None,
) -> AttendanceRecord | TrainerAttendance:
    """Create an open attendance record for a customer or trainer.

    Raises ``ValidationError`` for unsupported person types, unknown
    persons, and duplicate open check-ins on the same day.
    """
    today = timezone.localdate()
    now = timezone.now()

    if person_type == "customer":
        if not Customer.objects.for_tenant(tenant).filter(id=person_id).exists():
            raise ValidationError({"person_id": "Customer not found."})
        records = AttendanceRecord.objects.for_tenant(tenant)
        if records.filter(
            customer_id=person_id, date=today, check_out_time__isnull=True
        ).exists():
            raise ValidationError(
                {"detail": "Already checked in — check out first."}
            )
        record = AttendanceRecord(
            tenant=tenant,
            customer_id=person_id,
            branch_id=branch_id,
            check_in_time=now,
            method=AttendanceRecord.Method.MANUAL,
        )
        record.save()
        return record

    if person_type == "trainer":
        if not Trainer.objects.filter(id=person_id, user__tenant=tenant).exists():
            raise ValidationError({"person_id": "Trainer not found."})
        records = TrainerAttendance.objects.for_tenant(tenant)
        if records.filter(
            trainer_id=person_id, date=today, check_out_time__isnull=True
        ).exists():
            raise ValidationError(
                {"detail": "Already checked in — check out first."}
            )
        record = TrainerAttendance(
            tenant=tenant,
            trainer_id=person_id,
            branch_id=branch_id,
            check_in_time=now,
        )
        record.save()
        return record

    raise ValidationError({"person_type": "Staff attendance is not supported yet."})