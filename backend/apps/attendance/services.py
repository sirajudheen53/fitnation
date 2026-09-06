"""Attendance business logic services."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.attendance.models import (
    AttendanceRecord,
    StaffAttendance,
    TrainerAttendance,
)
from apps.customers.models import Customer
from apps.users.models import Trainer, User


def log_check_in(
    *,
    tenant,
    person_id: int,
    person_type: str,
    branch_id: int | None = None,
    status: str | None = None,
) -> AttendanceRecord | TrainerAttendance | StaffAttendance:
    """Create an attendance record for a customer, trainer, or staff member.

    Raises ``ValidationError`` for unknown persons, duplicate open
    check-ins on the same day, and customer ids passed as staff.
    """
    today = timezone.localdate()
    now = timezone.now()
    record_status = status or "present"

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
            status=record_status,
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
            status=record_status,
        )
        record.save()
        return record

    if person_type == "staff":
        staff_user = User.objects.filter(id=person_id, tenant=tenant).first()
        if staff_user is None:
            raise ValidationError({"person_id": "Staff member not found."})
        if staff_user.role == User.Role.CUSTOMER:
            raise ValidationError(
                {"person_id": "User is a customer — use the customer flow."}
            )
        records = StaffAttendance.objects.for_tenant(tenant)
        if records.filter(
            user_id=person_id, date=today, check_out_time__isnull=True
        ).exists():
            raise ValidationError({"detail": "Already checked in — check out first."})
        record = StaffAttendance(
            tenant=tenant,
            user_id=person_id,
            branch_id=branch_id,
            check_in_time=now,
            method=AttendanceRecord.Method.MANUAL,
            status=record_status,
        )
        record.save()
        return record

    raise ValidationError({"person_type": "Unsupported person type."})