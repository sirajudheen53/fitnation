"""Tests for the trainer session engine (issue #52).

Covers the ``TrainerSession`` model (constraints, tenant isolation), the PT
session-pack entitlement selector (pack math, expiry, window scoping,
cancel-restore), the booking/transition services (overlap guard, performance
feed) and the API surface (booking 409s, lifecycle actions, permission
scoping, ``pt-remaining``).
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import count

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.trainers.models import TrainerPerformance, TrainerSession
from apps.trainers.selectors import PTPackReason, get_pt_entitlement
from apps.trainers.services import (
    SessionBookingError,
    assert_no_slot_conflict,
    book_session,
    transition_session,
)
from apps.users.models import User
from apps.users.services import create_owner_user, create_user, issue_token
from apps.users.trainer_services import create_trainer


def _make_trainer(tenant, email="trainer@local.test"):
    """Create a trainer (user + profile) within a tenant."""
    return create_trainer(
        tenant=tenant,
        email=email,
        first_name="Alex",
        last_name="Trainer",
        specialization="Strength",
        max_clients=10,
    )


def _make_customer(tenant, email="customer@local.test"):
    """Create a customer within a tenant (profile auto-created by create_user)."""
    user = create_user(
        tenant=tenant,
        email=email,
        first_name="Casey",
        last_name="Customer",
        role=User.Role.CUSTOMER,
    )
    return user.customer_profile


_pack_seq = count()


def _make_pt_membership(
    tenant,
    customer,
    *,
    sessions_allowed=10,
    days=30,
    end_offset=None,
    name=None,
):
    """Sell a PT membership on a session-pack plan (or expired when end_offset < 0)."""
    plan = MembershipPlan.objects.create(
        tenant=tenant,
        name=name or f"PT Pack {next(_pack_seq)}",  # (tenant, name) is unique
        plan_type=MembershipPlan.PlanType.PT,
        price=Decimal("5000.00"),
        duration_days=days,
        sessions_allowed=sessions_allowed,
    )
    end_date = timezone.localdate() + (
        end_offset if end_offset is not None else timedelta(days=days)
    )
    return Membership.objects.create(
        tenant=tenant,
        customer=customer,
        plan=plan,
        start_date=timezone.localdate(),
        end_date=end_date,
    )


def _session_dt(days_ahead=0, hour=10, minute=0):
    """Return a tz-aware slot start on ``localdate() + days_ahead`` (settings TZ)."""
    naive = datetime.combine(timezone.localdate() + timedelta(days=days_ahead), time(hour, minute))
    return timezone.make_aware(naive)


def _make_session(tenant, trainer, customer, *, scheduled_at=None, status=TrainerSession.Status.BOOKED):
    """Create a TrainerSession row directly (bypasses the booking gates)."""
    return TrainerSession.objects.create(
        tenant=tenant,
        trainer=trainer,
        customer=customer,
        scheduled_at=scheduled_at or _session_dt(),
        status=status,
    )


class TrainerSessionModelTests(TestCase):
    """Unit tests for the TrainerSession model."""

    def setUp(self) -> None:
        """Create two isolated tenants with trainer/customer fixtures."""
        self.tenant_a = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.tenant_b = provision_tenant(name="Gym B", contact_email="b@local.test")
        self.trainer_a = _make_trainer(self.tenant_a, "a@trainer.test")
        self.customer_a = _make_customer(self.tenant_a, "a@customer.test")

    def test_session_requires_tenant(self) -> None:
        """Saving a session without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            TrainerSession.objects.create(
                trainer=self.trainer_a,
                customer=self.customer_a,
                scheduled_at=_session_dt(),
            )

    def test_session_defaults(self) -> None:
        """New sessions are booked, 60 minutes, and not redeemed."""
        session = _make_session(self.tenant_a, self.trainer_a, self.customer_a)
        self.assertEqual(session.status, TrainerSession.Status.BOOKED)
        self.assertEqual(session.duration_minutes, 60)
        self.assertFalse(session.is_redeemed)
        self.assertEqual(session.ends_at, session.scheduled_at + timedelta(minutes=60))

    def test_redeemed_statuses(self) -> None:
        """Completed and no_show redeem; booked and cancelled do not."""
        completed = _make_session(
            self.tenant_a, self.trainer_a, self.customer_a, status=TrainerSession.Status.COMPLETED
        )
        no_show = _make_session(
            self.tenant_a, self.trainer_a, self.customer_a, status=TrainerSession.Status.NO_SHOW
        )
        cancelled = _make_session(
            self.tenant_a, self.trainer_a, self.customer_a, status=TrainerSession.Status.CANCELLED
        )
        self.assertTrue(completed.is_redeemed)
        self.assertTrue(no_show.is_redeemed)
        self.assertFalse(cancelled.is_redeemed)

    def test_duration_check_constraint(self) -> None:
        """duration_minutes must be between 1 and 480."""
        session = _make_session(self.tenant_a, self.trainer_a, self.customer_a)
        session.duration_minutes = 0
        with self.assertRaises(IntegrityError), transaction.atomic():
            session.save()
        session.duration_minutes = 481
        with self.assertRaises(IntegrityError), transaction.atomic():
            session.save()
        session.duration_minutes = 480
        session.save()  # boundary is inclusive

    def test_session_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's sessions."""
        _make_session(self.tenant_a, self.trainer_a, self.customer_a)
        trainer_b = _make_trainer(self.tenant_b, "b@trainer.test")
        customer_b = _make_customer(self.tenant_b, "b@customer.test")
        _make_session(self.tenant_b, trainer_b, customer_b)
        self.assertEqual(TrainerSession.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(TrainerSession.objects.for_tenant(self.tenant_b).count(), 1)


class PTPackEntitlementTests(TestCase):
    """Tests for the PT session-pack entitlement selector."""

    def setUp(self) -> None:
        """Create a tenant with trainer and customer fixtures."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.trainer = _make_trainer(self.tenant)
        self.customer = _make_customer(self.tenant)

    def test_none_customer_returns_empty_state(self) -> None:
        """``None`` customer → no pack, cannot book."""
        pack = get_pt_entitlement(None)
        self.assertEqual(pack.membership_status, "none")
        self.assertEqual(pack.reason, PTPackReason.NO_ACTIVE_PT_MEMBERSHIP)
        self.assertFalse(pack.can_book)

    def test_no_membership(self) -> None:
        """No PT membership → booking rejected with the reason."""
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.membership_status, "none")
        self.assertEqual(pack.reason, PTPackReason.NO_ACTIVE_PT_MEMBERSHIP)
        self.assertEqual(pack.remaining, 0)
        self.assertFalse(pack.can_book)

    def test_non_pt_plan_grants_nothing(self) -> None:
        """An active monthly membership is not a session pack."""
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            plan_type=MembershipPlan.PlanType.MONTHLY,
            price=Decimal("2000.00"),
            duration_days=30,
            sessions_allowed=8,  # knob is inert on non-PT plans
        )
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.membership_status, "none")
        self.assertEqual(pack.reason, PTPackReason.NO_ACTIVE_PT_MEMBERSHIP)

    def test_pack_math(self) -> None:
        """remaining = sessions_allowed − (completed + no_show) in the window."""
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=10)
        _make_session(
            self.tenant, self.trainer, self.customer,
            scheduled_at=_session_dt(hour=9),
            status=TrainerSession.Status.COMPLETED,
        )
        _make_session(
            self.tenant, self.trainer, self.customer,
            scheduled_at=_session_dt(hour=11),
            status=TrainerSession.Status.NO_SHOW,
        )
        _make_session(self.tenant, self.trainer, self.customer, scheduled_at=_session_dt(hour=13))  # booked
        _make_session(
            self.tenant, self.trainer, self.customer,
            scheduled_at=_session_dt(hour=15),
            status=TrainerSession.Status.CANCELLED,
        )

        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.membership_status, "active")
        self.assertEqual(pack.sessions_allowed, 10)
        self.assertEqual(pack.redeemed, 2)
        self.assertEqual(pack.remaining, 8)
        self.assertEqual(pack.reason, PTPackReason.OK)
        self.assertTrue(pack.can_book)
        self.assertFalse(pack.unlimited)

    def test_unlimited_pack(self) -> None:
        """``sessions_allowed=None`` → unlimited, always bookable."""
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=None)
        _make_session(
            self.tenant, self.trainer, self.customer, status=TrainerSession.Status.COMPLETED
        )
        pack = get_pt_entitlement(self.customer)
        self.assertTrue(pack.unlimited)
        self.assertIsNone(pack.remaining)
        self.assertEqual(pack.redeemed, 1)
        self.assertTrue(pack.can_book)

    def test_expired_membership_rejected(self) -> None:
        """A PT membership past its end_date blocks booking."""
        _make_pt_membership(self.tenant, self.customer, end_offset=timedelta(days=-1))
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.membership_status, "expired")
        self.assertEqual(pack.reason, PTPackReason.PT_MEMBERSHIP_EXPIRED)
        self.assertFalse(pack.can_book)

    def test_cancelled_membership_ignored(self) -> None:
        """A cancelled PT membership counts as no membership."""
        membership = _make_pt_membership(self.tenant, self.customer)
        membership.status = Membership.Status.CANCELLED
        membership.save()
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.reason, PTPackReason.NO_ACTIVE_PT_MEMBERSHIP)

    def test_window_scoping(self) -> None:
        """Only sessions inside the active membership's window redeem."""
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=4)
        # Redeemed before the membership started, and after it ends — neither counts.
        _make_session(
            self.tenant, self.trainer, self.customer,
            scheduled_at=_session_dt(days_ahead=-10),
            status=TrainerSession.Status.COMPLETED,
        )
        _make_session(
            self.tenant, self.trainer, self.customer,
            scheduled_at=_session_dt(days_ahead=60),
            status=TrainerSession.Status.NO_SHOW,
        )
        # Inside the window — counts.
        _make_session(
            self.tenant, self.trainer, self.customer,
            status=TrainerSession.Status.COMPLETED,
        )
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.redeemed, 1)
        self.assertEqual(pack.remaining, 3)

    def test_cancel_restores_credit(self) -> None:
        """Cancelling a redeemed session gives the credit back (derived count)."""
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=2)
        session = _make_session(
            self.tenant, self.trainer, self.customer, status=TrainerSession.Status.COMPLETED
        )
        self.assertEqual(get_pt_entitlement(self.customer).remaining, 1)
        session.status = TrainerSession.Status.CANCELLED
        session.save()
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.redeemed, 0)
        self.assertEqual(pack.remaining, 2)

    def test_tenant_isolation_in_redemption_count(self) -> None:
        """Another tenant's session for a same-named customer never counts."""
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=2)
        other_tenant = provision_tenant(name="Other", contact_email="other@local.test")
        other_trainer = _make_trainer(other_tenant, "other@trainer.test")
        other_customer = _make_customer(other_tenant, "other@customer.test")
        _make_session(other_tenant, other_trainer, other_customer, status=TrainerSession.Status.COMPLETED)
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.redeemed, 0)


class TrainerSessionServiceTests(TestCase):
    """Tests for booking gates, the overlap guard, and the performance feed."""

    def setUp(self) -> None:
        """Create a tenant with an active 10-pack."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.trainer = _make_trainer(self.tenant)
        self.customer = _make_customer(self.tenant)
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=10)
        self.branch = None  # optional on sessions

    def test_book_session_creates_booked_row(self) -> None:
        """book_session persists a booked session under the tenant."""
        session = book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(),
        )
        self.assertEqual(session.status, TrainerSession.Status.BOOKED)
        self.assertEqual(session.tenant, self.tenant)

    def test_overlap_rejected(self) -> None:
        """A partially overlapping booked slot raises 409 trainer_slot_conflict."""
        book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10),
        )
        with self.assertRaises(SessionBookingError) as ctx:
            book_session(
                tenant=self.tenant,
                trainer=self.trainer,
                customer=self.customer,
                scheduled_at=_session_dt(hour=10, minute=30),
            )
        self.assertEqual(ctx.exception.detail["reason"], "trainer_slot_conflict")

    def test_contained_slot_rejected(self) -> None:
        """A slot fully inside an existing one conflicts."""
        book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10),
        )
        with self.assertRaises(SessionBookingError):
            book_session(
                tenant=self.tenant,
                trainer=self.trainer,
                customer=self.customer,
                scheduled_at=_session_dt(hour=10, minute=15),
            )

    def test_adjacent_slot_allowed(self) -> None:
        """Back-to-back slots do not conflict."""
        book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10),
        )
        session = book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=11),
        )
        self.assertEqual(session.status, TrainerSession.Status.BOOKED)

    def test_cancelled_session_frees_slot(self) -> None:
        """A cancelled session no longer blocks its slot."""
        session = book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10),
        )
        session.status = TrainerSession.Status.CANCELLED
        session.save()
        rebooked = book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10, minute=30),
        )
        self.assertEqual(rebooked.status, TrainerSession.Status.BOOKED)

    def test_other_trainer_no_conflict(self) -> None:
        """Overlap is per-trainer: another trainer can take the same slot."""
        book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10),
        )
        other_trainer = _make_trainer(self.tenant, "second@trainer.test")
        session = book_session(
            tenant=self.tenant,
            trainer=other_trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10, minute=30),
        )
        self.assertEqual(session.status, TrainerSession.Status.BOOKED)

    def test_reschedule_excludes_self(self) -> None:
        """Moving a session over its own old slot is allowed."""
        session = book_session(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            scheduled_at=_session_dt(hour=10),
        )
        assert_no_slot_conflict(
            tenant=self.tenant,
            trainer=self.trainer,
            scheduled_at=_session_dt(hour=10, minute=30),
            duration_minutes=60,
            exclude_pk=session.pk,
        )

    def test_book_without_membership_rejected(self) -> None:
        """Booking without a PT membership → 409 no_active_pt_membership."""
        walk_in = _make_customer(self.tenant, "walkin@customer.test")
        with self.assertRaises(SessionBookingError) as ctx:
            book_session(
                tenant=self.tenant,
                trainer=self.trainer,
                customer=walk_in,
                scheduled_at=_session_dt(),
            )
        self.assertEqual(ctx.exception.detail["reason"], PTPackReason.NO_ACTIVE_PT_MEMBERSHIP)

    def test_book_with_exhausted_pack_rejected(self) -> None:
        """Booking at 0 remaining → 409 session_pack_exhausted."""
        exhausted = _make_customer(self.tenant, "exhausted@customer.test")
        _make_pt_membership(self.tenant, exhausted, sessions_allowed=1)
        _make_session(
            self.tenant, self.trainer, exhausted, status=TrainerSession.Status.COMPLETED
        )
        with self.assertRaises(SessionBookingError) as ctx:
            book_session(
                tenant=self.tenant,
                trainer=self.trainer,
                customer=exhausted,
                scheduled_at=_session_dt(),
            )
        self.assertEqual(ctx.exception.detail["reason"], PTPackReason.PACK_EXHAUSTED)
        # DRF coerces exception-detail values to strings.
        self.assertEqual(str(ctx.exception.detail["remaining"]), "0")

    def test_invalid_transitions_rejected(self) -> None:
        """The lifecycle only allows forward moves into the three exits."""
        session = _make_session(self.tenant, self.trainer, self.customer)
        with self.assertRaises(ValidationError):
            transition_session(session, TrainerSession.Status.BOOKED)

        completed = _make_session(
            self.tenant, self.trainer, self.customer, status=TrainerSession.Status.COMPLETED
        )
        with self.assertRaises(ValidationError):
            transition_session(completed, TrainerSession.Status.NO_SHOW)

        cancelled = _make_session(
            self.tenant, self.trainer, self.customer, status=TrainerSession.Status.CANCELLED
        )
        with self.assertRaises(ValidationError):
            transition_session(cancelled, TrainerSession.Status.COMPLETED)

    def test_complete_feeds_performance(self) -> None:
        """Completing creates the monthly record with +1 session."""
        session = _make_session(self.tenant, self.trainer, self.customer, scheduled_at=_session_dt())
        transition_session(session, TrainerSession.Status.COMPLETED)
        record = TrainerPerformance.objects.get(tenant=self.tenant, trainer=self.trainer)
        self.assertEqual(record.month, _session_dt().date().replace(day=1))
        self.assertEqual(record.sessions_completed, 1)

    def test_no_show_feeds_performance(self) -> None:
        """No-show redeems a credit and feeds the performance aggregate."""
        session = _make_session(self.tenant, self.trainer, self.customer)
        transition_session(session, TrainerSession.Status.NO_SHOW)
        record = TrainerPerformance.objects.get(tenant=self.tenant, trainer=self.trainer)
        self.assertEqual(record.sessions_completed, 1)

    def test_cancel_after_complete_restores_performance(self) -> None:
        """Cancelling a redeemed session decrements the monthly aggregate."""
        session = _make_session(self.tenant, self.trainer, self.customer)
        transition_session(session, TrainerSession.Status.COMPLETED)
        transition_session(session, TrainerSession.Status.CANCELLED)
        record = TrainerPerformance.objects.get(tenant=self.tenant, trainer=self.trainer)
        self.assertEqual(record.sessions_completed, 0)

    def test_performance_monthly_buckets(self) -> None:
        """Sessions in different months feed different monthly records."""
        early = _make_session(
            self.tenant, self.trainer, self.customer, scheduled_at=_session_dt(days_ahead=-40)
        )
        late = _make_session(
            self.tenant, self.trainer, self.customer, scheduled_at=_session_dt(days_ahead=40)
        )
        transition_session(early, TrainerSession.Status.COMPLETED)
        transition_session(late, TrainerSession.Status.NO_SHOW)
        self.assertEqual(TrainerPerformance.objects.filter(tenant=self.tenant).count(), 2)
        totals = {r.month.month: r.sessions_completed for r in TrainerPerformance.objects.all()}
        self.assertEqual(sorted(totals.values()), [1, 1])


class TrainerSessionAPITests(APITestCase):
    """Integration tests for the trainer-sessions + pt-remaining endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner auth, trainer, customer, and a 2-session pack."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {issue_token(self.owner, self.tenant).key}")
        self.trainer = _make_trainer(self.tenant)
        self.customer = _make_customer(self.tenant)
        self.membership = _make_pt_membership(self.tenant, self.customer, sessions_allowed=2)
        self.branch = None  # branches are optional on sessions

    def _booking_payload(self, *, trainer=None, customer=None, scheduled_at=None, **extra):
        """Return a valid booking payload."""
        slot = scheduled_at or _session_dt()
        payload = {
            "trainer": (trainer or self.trainer).id,
            "customer": (customer or self.customer).id,
            "scheduled_at": slot.isoformat() if isinstance(slot, datetime) else slot,
            "duration_minutes": 60,
            "notes": "bring lifting belt",
        }
        payload.update(extra)
        return payload

    def _book(self, **kwargs):
        """POST a booking and return the response."""
        return self.client.post("/api/v1/trainer-sessions/", self._booking_payload(**kwargs))

    def _complete(self, session_id):
        """POST the complete action."""
        return self.client.post(f"/api/v1/trainer-sessions/{session_id}/complete/")

    def test_book_session(self) -> None:
        """Owners can book a session; the response echoes the booking."""
        response = self._book(scheduled_at=_session_dt(hour=10).isoformat())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "booked")
        self.assertEqual(response.data["trainer_email"], self.trainer.user.email)
        self.assertEqual(response.data["customer_name"], self.customer.name)
        self.assertEqual(response.data["duration_minutes"], 60)
        self.assertEqual(response.data["notes"], "bring lifting belt")

    def test_pack_boundary(self) -> None:
        """A 2-pack allows exactly 2 redemptions; the next booking is a 409."""
        first = self._book(scheduled_at=_session_dt(hour=8).isoformat())
        second = self._book(scheduled_at=_session_dt(hour=10).isoformat())
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        # Booked sessions don't consume credits — completing both does.
        self.assertEqual(self._complete(first.data["id"]).status_code, 200)
        self.client.post(f"/api/v1/trainer-sessions/{second.data['id']}/no-show/")
        self.assertEqual(get_pt_entitlement(self.customer).remaining, 0)

        response = self._book(scheduled_at=_session_dt(hour=12).isoformat())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reason"], "session_pack_exhausted")
        self.assertEqual(str(response.data["remaining"]), "0")

    def test_booking_without_pt_membership(self) -> None:
        """Booking for a customer with no PT membership → 409 with reason."""
        walk_in = _make_customer(self.tenant, "walkin@customer.test")
        response = self._book(customer=walk_in)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reason"], "no_active_pt_membership")

    def test_booking_with_expired_membership(self) -> None:
        """Booking against an expired PT membership → 409 with reason."""
        expired = _make_customer(self.tenant, "expired@customer.test")
        _make_pt_membership(self.tenant, expired, end_offset=timedelta(days=-1))
        response = self._book(customer=expired)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reason"], "pt_membership_expired")

    def test_booking_with_monthly_plan_only(self) -> None:
        """A non-PT membership grants no session pack → 409."""
        monthly = _make_customer(self.tenant, "monthly@customer.test")
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            plan_type=MembershipPlan.PlanType.MONTHLY,
            price=Decimal("2000.00"),
            duration_days=30,
        )
        Membership.objects.create(
            tenant=self.tenant,
            customer=monthly,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        response = self._book(customer=monthly)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reason"], "no_active_pt_membership")

    def test_overlap_booking_409(self) -> None:
        """Overlapping slot booking → 409 trainer_slot_conflict."""
        self._book(scheduled_at=_session_dt(hour=10).isoformat())
        response = self._book(scheduled_at=_session_dt(hour=10, minute=30).isoformat())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reason"], "trainer_slot_conflict")

    def test_complete_and_remaining(self) -> None:
        """Complete redeems one credit and feeds trainer performance."""
        response = self._book()
        session_id = response.data["id"]
        completed = self._complete(session_id)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["status"], "completed")

        remaining = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/pt-remaining/")
        self.assertEqual(remaining.status_code, 200)
        self.assertEqual(remaining.data["redeemed"], 1)
        self.assertEqual(remaining.data["remaining"], 1)

        record = TrainerPerformance.objects.get(tenant=self.tenant, trainer=self.trainer)
        self.assertEqual(record.sessions_completed, 1)

    def test_no_show_action(self) -> None:
        """The no-show action marks the session and redeems a credit."""
        response = self._book()
        no_show = self.client.post(f"/api/v1/trainer-sessions/{response.data['id']}/no-show/")
        self.assertEqual(no_show.status_code, 200)
        self.assertEqual(no_show.data["status"], "no_show")
        self.assertEqual(get_pt_entitlement(self.customer).redeemed, 1)

    def test_cancel_does_not_redeem(self) -> None:
        """Cancelled sessions never redeem a credit."""
        response = self._book()
        cancelled = self.client.post(f"/api/v1/trainer-sessions/{response.data['id']}/cancel/")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data["status"], "cancelled")
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.redeemed, 0)
        self.assertEqual(pack.remaining, 2)

    def test_cancel_after_complete_restores_credit(self) -> None:
        """Cancelling a completed session restores the pack credit."""
        response = self._book()
        self._complete(response.data["id"])
        self.client.post(f"/api/v1/trainer-sessions/{response.data['id']}/cancel/")
        pack = get_pt_entitlement(self.customer)
        self.assertEqual(pack.redeemed, 0)
        self.assertEqual(pack.remaining, 2)

    def test_complete_twice_rejected(self) -> None:
        """Completing an already-completed session is a 400."""
        response = self._book()
        self._complete(response.data["id"])
        again = self._complete(response.data["id"])
        self.assertEqual(again.status_code, 400)

    def test_reschedule_via_patch(self) -> None:
        """PATCH moves a slot; moving over its own old time is allowed."""
        response = self._book(scheduled_at=_session_dt(hour=10).isoformat())
        session_id = response.data["id"]
        moved = self.client.patch(
            f"/api/v1/trainer-sessions/{session_id}/",
            {"scheduled_at": _session_dt(hour=10, minute=30).isoformat()},
            format="json",
        )
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.data["status"], "booked")

    def test_reschedule_conflict_409(self) -> None:
        """PATCH into another session's slot → 409."""
        self._book(scheduled_at=_session_dt(hour=8).isoformat())
        target = self._book(scheduled_at=_session_dt(hour=10).isoformat())
        response = self.client.patch(
            f"/api/v1/trainer-sessions/{target.data['id']}/",
            {"scheduled_at": _session_dt(hour=8, minute=30).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reason"], "trainer_slot_conflict")

    def test_pt_remaining_endpoint(self) -> None:
        """The pt-remaining payload carries membership, total, redeemed, remaining."""
        _make_session(
            self.tenant, self.trainer, self.customer, status=TrainerSession.Status.COMPLETED
        )
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/pt-remaining/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["customer_id"], self.customer.id)
        self.assertEqual(response.data["membership_id"], self.membership.id)
        self.assertEqual(response.data["plan_name"], self.membership.plan.name)
        self.assertEqual(response.data["membership_status"], "active")
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(response.data["redeemed"], 1)
        self.assertEqual(response.data["remaining"], 1)
        self.assertFalse(response.data["unlimited"])
        self.assertTrue(response.data["can_book"])
        self.assertEqual(response.data["reason"], "ok")

    def test_pt_remaining_without_membership(self) -> None:
        """A customer with no PT pack reports the blocked reason."""
        walk_in = _make_customer(self.tenant, "walkin@customer.test")
        response = self.client.get(f"/api/v1/customers/customers/{walk_in.id}/pt-remaining/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["membership_id"])
        self.assertEqual(response.data["reason"], "no_active_pt_membership")
        self.assertFalse(response.data["can_book"])

    def test_session_list_filter_by_status(self) -> None:
        """The list endpoint filters by status."""
        booked = self._book(scheduled_at=_session_dt(hour=8).isoformat())
        self._complete(booked.data["id"])
        self._book(scheduled_at=_session_dt(hour=10).isoformat())

        response = self.client.get("/api/v1/trainer-sessions/?status=booked")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        response = self.client.get("/api/v1/trainer-sessions/?status=completed")
        self.assertEqual(len(response.data), 1)

    def test_cross_tenant_trainer_rejected(self) -> None:
        """Booking a trainer from another tenant fails validation."""
        other_tenant = provision_tenant(name="Other", contact_email="other@local.test")
        other_trainer = _make_trainer(other_tenant, "other@trainer.test")
        response = self._book(trainer=other_trainer)
        self.assertEqual(response.status_code, 400)

    def test_cross_tenant_session_404(self) -> None:
        """Sessions of another tenant are invisible."""
        other_tenant = provision_tenant(name="Other", contact_email="other@local.test")
        other_trainer = _make_trainer(other_tenant, "other@trainer.test")
        other_customer = _make_customer(other_tenant, "other@customer.test")
        session = _make_session(other_tenant, other_trainer, other_customer)
        response = self.client.get(f"/api/v1/trainer-sessions/{session.id}/")
        self.assertEqual(response.status_code, 404)

    def test_session_list_tenant_scoped(self) -> None:
        """The session list only shows the authenticated tenant's rows."""
        self._book()
        other_tenant = provision_tenant(name="Other", contact_email="other@local.test")
        other_trainer = _make_trainer(other_tenant, "other@trainer.test")
        other_customer = _make_customer(other_tenant, "other@customer.test")
        _make_session(other_tenant, other_trainer, other_customer)
        response = self.client.get("/api/v1/trainer-sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class SessionPermissionScopingTests(APITestCase):
    """Role-scoping tests for the trainers.* permission codes (issue #52)."""

    def setUp(self) -> None:
        """Create tenant, staff roles, customer, and a PT pack."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.trainer = _make_trainer(self.tenant, "trainer@local.test")
        self.customer = _make_customer(self.tenant, "customer@local.test")
        _make_pt_membership(self.tenant, self.customer, sessions_allowed=5)

    def _login(self, user) -> None:
        """Authenticate the API client as ``user``."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {issue_token(user, self.tenant).key}")

    def test_manager_can_book_and_complete(self) -> None:
        """Managers hold trainers.edit_session — book and transition sessions."""
        manager = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manager",
            last_name="One",
            role=User.Role.MANAGER,
        )
        self._login(manager)
        response = self.client.post(
            "/api/v1/trainer-sessions/",
            {
                "trainer": self.trainer.id,
                "customer": self.customer.id,
                "scheduled_at": _session_dt().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201)
        completed = self.client.post(f"/api/v1/trainer-sessions/{response.data['id']}/complete/")
        self.assertEqual(completed.status_code, 200)

    def test_trainer_role_can_view_and_run_sessions_but_not_assign(self) -> None:
        """Trainers get view_session/edit_session but not edit_trainer."""
        self._login(self.trainer.user)
        listed = self.client.get("/api/v1/trainer-sessions/")
        self.assertEqual(listed.status_code, 200)

        response = self.client.post(
            "/api/v1/trainer-sessions/",
            {
                "trainer": self.trainer.id,
                "customer": self.customer.id,
                "scheduled_at": _session_dt().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201)
        completed = self.client.post(f"/api/v1/trainer-sessions/{response.data['id']}/complete/")
        self.assertEqual(completed.status_code, 200)

        denied = self.client.post(
            "/api/v1/trainer-assignments/",
            {"trainer": self.trainer.id, "customer": self.customer.id},
        )
        self.assertEqual(denied.status_code, 403)

    def test_customer_role_blocked_from_session_endpoints(self) -> None:
        """Customers have neither view_session nor edit_session."""
        self._login(self.customer.user)
        listed = self.client.get("/api/v1/trainer-sessions/")
        self.assertEqual(listed.status_code, 403)
        booked = self.client.post(
            "/api/v1/trainer-sessions/",
            {
                "trainer": self.trainer.id,
                "customer": self.customer.id,
                "scheduled_at": _session_dt().isoformat(),
            },
        )
        self.assertEqual(booked.status_code, 403)

    def test_customer_can_check_own_pt_remaining(self) -> None:
        """Members may read their own pack state (view_customer + self-filter)."""
        self._login(self.customer.user)
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/pt-remaining/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["remaining"], 5)

    def test_customer_cannot_check_other_pt_remaining(self) -> None:
        """A member cannot read another customer's pack state."""
        other = _make_customer(self.tenant, "other@customer.test")
        _make_pt_membership(self.tenant, other, sessions_allowed=5)
        self._login(self.customer.user)
        response = self.client.get(f"/api/v1/customers/customers/{other.id}/pt-remaining/")
        self.assertEqual(response.status_code, 404)
