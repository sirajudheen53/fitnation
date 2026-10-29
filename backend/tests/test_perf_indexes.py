"""Composite-index guards for the hot query paths (issue #82).

The perf fixes in #82 lean on composite indexes; these tests pin that the
model metadata keeps declaring them, so removing one fails a test instead of
silently regressing the dashboard/list queries. The migrations themselves are
exercised by CI's Postgres run.
"""

from __future__ import annotations

from apps.attendance.models import AttendanceRecord
from apps.customers.models import Customer
from apps.memberships.models import Membership
from apps.notifications.models import NotificationLog
from apps.payments.models import Payment


def _index_columns(model, name: str) -> list[str] | None:
    """Return the ordered column list of an index by name, or None."""
    for index in model._meta.indexes:
        if index.name == name:
            return list(index.fields)
    return None


def test_payment_revenue_and_queue_indexes():
    """Completed-payment range scans and the pending queue order are indexed."""
    assert _index_columns(Payment, "idx_pay_tenant_status_paid") == ["tenant", "status", "paid_at"]
    assert _index_columns(Payment, "idx_pay_tenant_status_created") == ["tenant", "status", "created_at"]


def test_membership_status_and_end_date_indexes():
    """Status counts and the lapsed-dues range scan are indexed."""
    assert _index_columns(Membership, "idx_membership_tenant_status") == ["tenant", "status"]
    assert _index_columns(Membership, "idx_membership_tenant_end") == ["tenant", "end_date"]


def test_attendance_tenant_date_index():
    """Today-count and weekly-trend (tenant, date) scans are indexed."""
    assert _index_columns(AttendanceRecord, "idx_att_tenant_date") == ["tenant", "date"]


def test_notification_customer_invite_index():
    """The app-invite lookup (customer, type, newest) is indexed."""
    assert _index_columns(NotificationLog, "idx_notif_cust_type_created") == [
        "customer",
        "notification_type",
        "created_at",
    ]


def test_customer_list_order_index():
    """The member list's (tenant, created_at) default ordering is indexed."""
    assert _index_columns(Customer, "idx_customer_tenant_created") == ["tenant", "created_at"]
