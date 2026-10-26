"""Attendance business logic services."""

from datetime import timedelta

from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.attendance.models import (
    AUTO_CHECKOUT_AFTER,
    AttendanceRecord,
    StaffAttendance,
    TrainerAttendance,
)
from apps.customers.models import Customer
from apps.users.models import Trainer, User

#: Punches landing sooner than this after check_in are duplicate
#: double-reads of the same biometric scan, not a real check-out.
DOUBLE_READ_WINDOW = timedelta(seconds=60)


def apply_auto_checkouts(*, tenant, now=None, dry_run: bool = False) -> int:
    """Auto-close the tenant's open check-ins that passed check-in + 2h.

    Issue #83: the biometric hardware has no check-out punch, so unpaired
    check-ins linger open forever. One atomic UPDATE stamps every eligible
    row with ``check_out_time = check_in_time + AUTO_CHECKOUT_AFTER``,
    flags it ``check_out_is_auto`` and flips status to ``left`` — rows
    with a real check-out (punch or manual) are excluded by the
    ``check_out_time__isnull`` filter, so real values are never touched
    and re-runs are no-ops (idempotent).

    Runs at punch-ingestion time and inside the manual check-in flow;
    ``auto_checkout_backfill`` schedules it across all tenants externally
    (Cloud Run has no beat/worker).

    Args:
        tenant: Tenant whose records are swept.
        now: Override "now" (tests); defaults to the current time.
        dry_run: Count eligible rows without writing.

    Returns:
        Number of rows stamped (or eligible, when ``dry_run``).
    """
    now = now or timezone.now()
    queryset = AttendanceRecord.objects.for_tenant(tenant).filter(
        check_out_time__isnull=True,
        check_in_time__lte=now - AUTO_CHECKOUT_AFTER,
    )
    if dry_run:
        return queryset.count()
    return queryset.update(
        check_out_time=F("check_in_time") + AUTO_CHECKOUT_AFTER,
        check_out_is_auto=True,
        status=AttendanceRecord.Status.LEFT,
        updated_at=now,
    )


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
        # Issue #83: sweep first so a member whose earlier visit already
        # passed check-in + 2h is freed for a fresh check-in instead of
        # tripping the duplicate guard against a zombie open record.
        apply_auto_checkouts(tenant=tenant, now=now)
        if not Customer.objects.for_tenant(tenant).filter(id=person_id).exists():
            raise ValidationError({"person_id": "Customer not found."})
        records = AttendanceRecord.objects.for_tenant(tenant)
        if records.filter(customer_id=person_id, date=today, check_out_time__isnull=True).exists():
            raise ValidationError({"detail": "Already checked in — check out first."})
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
        if records.filter(trainer_id=person_id, date=today, check_out_time__isnull=True).exists():
            raise ValidationError({"detail": "Already checked in — check out first."})
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
            raise ValidationError({"person_id": "User is a customer — use the customer flow."})
        records = StaffAttendance.objects.for_tenant(tenant)
        if records.filter(user_id=person_id, date=today, check_out_time__isnull=True).exists():
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


def pair_punch(*, tenant, customer: Customer, branch, punch_ts) -> dict:
    """Fold one biometric punch into the customer's day attendance record.

    State machine per (customer, branch, local date) — phase 2 punch
    pairing:

    - no record that day → open one (``check_in`` = punch, method
      ``biometric``);
    - open record → a punch ≥60s after ``check_in`` closes it; sooner is
      a duplicate double-read and is ignored;
    - closed record → a later punch moves ``check_out`` (last punch of
      the day wins); ``check_in`` always stays the first punch;
    - auto-closed record (issue #83, ``check_out_is_auto``) → any real
      punch ≥60s after ``check_in`` replaces the derived value, even one
      earlier than the auto stamp — the +2h guess never wins over a
      punch, and the flag clears.

    Args:
        tenant: Tenant scope for the record lookup/creation.
        customer: The resolved puncher.
        branch: The punching device's branch (even when the customer was
            resolved via a credential enrolled on another device).
        punch_ts: Timezone-aware punch time.

    Returns:
        ``{"record": AttendanceRecord, "outcome": str}`` with outcome one
        of ``checked_in`` / ``checked_out`` / ``check_out_updated`` /
        ``auto_check_out_overridden`` / ``double_read_ignored`` /
        ``stale_punch_ignored``.
    """
    local_date = timezone.localdate(punch_ts)
    records = list(
        AttendanceRecord.objects.for_tenant(tenant)
        .filter(customer=customer, branch=branch, date=local_date)
        .order_by("check_in_time", "pk")
    )

    if not records:
        record = AttendanceRecord(
            tenant=tenant,
            customer=customer,
            branch=branch,
            check_in_time=punch_ts,
            date=local_date,
            method=AttendanceRecord.Method.BIOMETRIC,
        )
        record.save()
        return {"record": record, "outcome": "checked_in"}

    open_record = next((r for r in records if r.check_out_time is None), None)
    if open_record is not None:
        if punch_ts - open_record.check_in_time >= DOUBLE_READ_WINDOW:
            open_record.check_out_time = punch_ts
            open_record.save(update_fields=["check_out_time", "updated_at"])
            return {"record": open_record, "outcome": "checked_out"}
        return {"record": open_record, "outcome": "double_read_ignored"}

    last = records[-1]
    if last.check_out_time is not None and last.check_out_is_auto:
        # Issue #83: the stored check-out is only the +2h derivation. A
        # real punch replaces it whatever its position relative to the
        # guess — earlier (late-arriving true check-out) or later.
        if punch_ts - last.check_in_time < DOUBLE_READ_WINDOW:
            return {"record": last, "outcome": "double_read_ignored"}
        last.check_out_time = punch_ts
        last.check_out_is_auto = False
        last.save(update_fields=["check_out_time", "check_out_is_auto", "updated_at"])
        return {"record": last, "outcome": "auto_check_out_overridden"}
    if punch_ts > last.check_out_time:
        last.check_out_time = punch_ts
        last.save(update_fields=["check_out_time", "updated_at"])
        return {"record": last, "outcome": "check_out_updated"}
    return {"record": last, "outcome": "stale_punch_ignored"}
