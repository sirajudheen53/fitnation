"""
Seed realistic, interconnected test data for the FitNation QA/dev server.

Usage::

    cd ~/development/fitnation/backend
    python manage.py seed_realistic_data

The command is idempotent: it uses ``get_or_create`` and skips records that
already exist, so it is safe to run repeatedly against the same database.

What it seeds (for the existing "FitNation Test Gym" tenant):
    - Tenant settings
    - Staff users (gym owner, manager, 3 trainers, dietitian)
    - 20 customers with realistic Indian names / Mumbai addresses
    - 2 additional branches (Andheri West, Bandra East)
    - Trainer profiles + weekly schedules
    - Customer profiles, health profiles, fitness goals
    - 5 membership plans, memberships (active/expired/cancelled), payments
    - Trainer assignments (branch-scoped + direct)
    - Exercise categories (incl. Sports) + workout plans/days/exercises
    - Customer workout assignments
    - Diet plans/days/meals + diet assignments
    - Attendance records for the past 30 days
    - Customer feedback
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.branches.models import Branch, BranchTrainerAssignment
from apps.customers.models import (
    Customer,
    FitnessGoal,
    HealthProfile,
)
from apps.diet.models import (
    DietAssignment,
    DietDay,
    DietMeal,
    DietPlan,
    FoodItem,
)
from apps.exercises.models import Exercise, ExerciseCategory
from apps.feedback.models import Feedback
from apps.memberships.models import Membership, MembershipPlan
from apps.payments.models import Payment
from apps.tenants.models import Tenant, TenantSettings
from apps.trainers.models import TrainerAssignment
from apps.users.models import Trainer, TrainerCustomerAssignment, TrainerSchedule, User
from apps.workouts.models import (
    WorkoutAssignment,
    WorkoutDay,
    WorkoutExercise,
    WorkoutPlan,
)

# ─── Deterministic RNG so re-runs produce the same "random" data ───────────
RNG = random.Random(42)


def _today() -> date:
    """Return the local server date."""
    return timezone.localdate()


def _dt(days_ago: int, hour: int = 9, minute: int = 0) -> datetime:
    """Return a timezone-aware datetime ``days_ago`` days back at ``hour:minute``."""
    return timezone.make_aware(datetime.combine(_today() - timedelta(days=days_ago), time(hour, minute)))


# ─── Realistic Indian data pools ────────────────────────────────────────────

_FIRST_NAMES_M = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Vihaan",
    "Arjun",
    "Sai",
    "Reyansh",
    "Krishna",
    "Ishaan",
    "Kabir",
    "Rohan",
    "Aryan",
    "Dev",
    "Karan",
    "Nikhil",
    "Rahul",
    "Amit",
    "Vikram",
    "Sanjay",
    "Manoj",
    "Ritesh",
    "Naveen",
    "Pranav",
    "Harsha",
]
_FIRST_NAMES_F = [
    "Aanya",
    "Diya",
    "Ananya",
    "Saanvi",
    "Ishita",
    "Anika",
    "Sneha",
    "Riya",
    "Pooja",
    "Neha",
    "Divya",
    "Tanvi",
    "Simran",
    "Anushka",
    "Meghna",
    "Kirti",
    "Charu",
    "Lakshmi",
    "Swati",
    "Zoya",
    "Nidhi",
    "Anjali",
    "Priya",
    "Kavya",
]
_LAST_NAMES = [
    "Sharma",
    "Verma",
    "Gupta",
    "Mehta",
    "Patel",
    "Joshi",
    "Nair",
    "Iyer",
    "Reddy",
    "Rao",
    "Singh",
    "Kumar",
    "Chawla",
    "Bhat",
    "Menon",
    "Trivedi",
    "Sarkar",
    "Bhatt",
    "Khatri",
    "Gowda",
    "Pillai",
    "Krish",
    "Sodhi",
    "Bansal",
    "Malik",
    "Bisht",
    "Ahmed",
    "Kaur",
    "Nayak",
    "Chopra",
]
_MUMBAI_STREETS = [
    "Linking Road, Bandra West",
    "Hill Road, Bandra West",
    "Carter Road, Bandra West",
    "SV Road, Andheri West",
    "Veera Desai Road, Andheri West",
    "New Link Road, Andheri West",
    "Linking Road, Khar West",
    "Pali Hill, Bandra West",
    "Juhu Tara Road, Juhu",
    "Waterfield Road, Bandra West",
    "Four Bungalows, Andheri West",
    "Versova, Andheri West",
    "Marine Drive, Churchgate",
    "Bandra Kurla Complex",
    "Worli Sea Face, Worli",
    "Pedder Road, Cumballa Hill",
    "Altamount Road, Malabar Hill",
    "Colaba Causeway, Colaba",
    "Lokhandwala Complex, Andheri West",
    "Beverly Park, Mira Road",
]
_EMERGENCY_NAMES = [
    "Rajesh Kumar",
    "Sunita Devi",
    "Amitabh Sharma",
    "Meena Patel",
    "Vikram Singh",
    "Lakshmi Iyer",
    "Suresh Nair",
    "Geeta Joshi",
    "Ramesh Gupta",
    "Kavita Rao",
]
_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
_GOAL_TYPES = [
    "lose_weight",
    "build_muscle",
    "endurance",
    "flexibility",
    "general_fitness",
    "sport_specific",
]
_GOAL_TARGETS = {
    "lose_weight": (5.0, 20.0, "kg"),
    "build_muscle": (2.0, 8.0, "kg"),
    "endurance": (30.0, 60.0, "min"),
    "flexibility": (10.0, 30.0, "min"),
    "general_fitness": (30.0, 90.0, "days"),
    "sport_specific": (10.0, 30.0, "sessions"),
}
_FEEDBACK_COMMENTS = [
    "Great atmosphere and very supportive trainers.",
    "The equipment is well maintained and clean.",
    "Love the group classes, they keep me motivated.",
    "Trainer was very helpful with my form correction.",
    "The diet plan really helped me reach my goals.",
    "Facility could use more squat racks during peak hours.",
    "Very professional staff and welcoming environment.",
    "The app makes it easy to track my workouts.",
    "Excellent value for money with the yearly plan.",
    "The new branch in Andheri is very convenient for me.",
    "Personal training sessions are worth every rupee.",
    "The nutrition guidance was practical and easy to follow.",
    "Great community, I look forward to coming every day.",
    "The locker rooms are always clean and tidy.",
    "Would love more evening classes on weekends.",
]


class Command(BaseCommand):
    """Seed realistic interconnected data for QA/dev testing."""

    help = "Seed realistic, interconnected test data for the FitNation QA/dev server."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            type=int,
            default=1,
            help="Tenant id to seed data for (default: 1 = FitNation Test Gym).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Tenant id={tenant_id} not found."))
            return

        self.stdout.write(self.style.SUCCESS(f"Seeding data for tenant: {tenant.name}"))

        # 1. Tenant settings
        self._seed_tenant_settings(tenant)

        # 2. Users (staff + customers)
        staff = self._seed_staff_users(tenant)
        customers = self._seed_customer_users(tenant)

        # 3. Branches
        branches = self._seed_branches(tenant)

        # 4. Trainer profiles
        trainers = self._seed_trainer_profiles(staff)

        # 5. Trainer schedules
        self._seed_trainer_schedules(tenant, trainers)

        # 6. Customer profiles
        customer_profiles = self._seed_customer_profiles(tenant, customers, branches)

        # 7. Health profiles
        self._seed_health_profiles(tenant, customer_profiles)

        # 8. Fitness goals
        self._seed_fitness_goals(tenant, customer_profiles)

        # 9. Membership plans
        plans = self._seed_membership_plans(tenant)

        # 10. Memberships
        memberships = self._seed_memberships(tenant, customer_profiles, plans)

        # 11. Payments
        self._seed_payments(tenant, customer_profiles, memberships)

        # 12. Trainer assignments
        self._seed_trainer_assignments(tenant, trainers, customer_profiles, branches)

        # 13. Exercise categories
        categories = self._seed_exercise_categories(tenant)

        # 14. Workout plans
        workout_plans = self._seed_workout_plans(tenant, categories, staff)

        # 15. Workout days & exercises
        self._seed_workout_days(tenant, workout_plans, categories)

        # 16. Customer workout assignments
        self._seed_workout_assignments(tenant, customer_profiles, workout_plans, staff)

        # 17. Diet plans
        diet_plans = self._seed_diet_plans(tenant)

        # 18. Diet assignments
        self._seed_diet_assignments(tenant, customer_profiles, diet_plans, staff)

        # 19. Attendance records
        self._seed_attendance(tenant, customer_profiles, branches)

        # 20. Feedback
        self._seed_feedback(tenant, customer_profiles, staff)

        self.stdout.write(self.style.SUCCESS("✅ Seed complete."))

    # ─── 1. Tenant settings ────────────────────────────────────────────────
    def _seed_tenant_settings(self, tenant):
        settings, created = TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                "max_branches": 5,
                "max_customers": 500,
                "max_trainers": 20,
                "primary_color": "#2563EB",
                "enable_whatsapp": True,
                "enable_razorpay": True,
                "custom_domain": "fitnation.test",
            },
        )
        self._report("Tenant settings", created)

    # ─── 2. Users ──────────────────────────────────────────────────────────
    def _seed_staff_users(self, tenant):
        staff_specs = [
            {
                "email": "owner@fitnation.test",
                "first_name": "Rajesh",
                "last_name": "Mehta",
                "role": User.Role.GYM_OWNER,
                "is_owner": True,
                "password": "GymOwner123!",
                "phone": "+91 98200 10001",
            },
            {
                "email": "manager@fitnation.test",
                "first_name": "Priya",
                "last_name": "Sharma",
                "role": User.Role.MANAGER,
                "is_owner": False,
                "password": "Manager123!",
                "phone": "+91 98200 10002",
            },
            {
                "email": "trainer1@fitnation.test",
                "first_name": "Arjun",
                "last_name": "Singh",
                "role": User.Role.TRAINER,
                "is_owner": False,
                "password": "Trainer123!",
                "phone": "+91 98200 10003",
            },
            {
                "email": "trainer2@fitnation.test",
                "first_name": "Vikram",
                "last_name": "Nair",
                "role": User.Role.TRAINER,
                "is_owner": False,
                "password": "Trainer123!",
                "phone": "+91 98200 10004",
            },
            {
                "email": "trainer3@fitnation.test",
                "first_name": "Kavita",
                "last_name": "Iyer",
                "role": User.Role.TRAINER,
                "is_owner": False,
                "password": "Trainer123!",
                "phone": "+91 98200 10005",
            },
            {
                "email": "dietitian@fitnation.test",
                "first_name": "Neha",
                "last_name": "Patel",
                "role": User.Role.DIETITIAN,
                "is_owner": False,
                "password": "Dietitian123!",
                "phone": "+91 98200 10006",
            },
        ]
        staff = {}
        for spec in staff_specs:
            user, created = User.objects.get_or_create(
                email=spec["email"],
                defaults={
                    "tenant": tenant,
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "role": spec["role"],
                    "is_owner": spec["is_owner"],
                    "phone": spec["phone"],
                    "is_staff": spec["role"]
                    in (
                        User.Role.GYM_OWNER,
                        User.Role.MANAGER,
                        User.Role.DIETITIAN,
                    ),
                },
            )
            if created:
                user.set_password(spec["password"])
                user.save()
            staff[spec["role"]] = user
            self._report(f"User {spec['email']}", created)
        return staff

    def _seed_customer_users(self, tenant):
        customers = []
        for i in range(1, 21):
            gender = "male" if i % 2 == 1 else "female"
            first = RNG.choice(_FIRST_NAMES_M if gender == "male" else _FIRST_NAMES_F)
            last = RNG.choice(_LAST_NAMES)
            email = f"customer{i}@example.com"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "tenant": tenant,
                    "first_name": first,
                    "last_name": last,
                    "role": User.Role.CUSTOMER,
                    "is_owner": False,
                    "phone": f"+91 9{RNG.randint(100000000, 999999999)}",
                },
            )
            if created:
                user.set_password("Customer123!")
                user.save()
            customers.append(user)
            self._report(f"Customer user {email}", created)
        return customers

    # ─── 3. Branches ──────────────────────────────────────────────────────
    def _seed_branches(self, tenant):
        branch_specs = [
            {
                "name": "Andheri West",
                "branch_type": Branch.BranchType.SUB,
                "address_line1": "Veera Desai Road, Andheri West",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400053",
                "phone": "+91 98200 20001",
                "email": "andheri@fitnation.test",
                "latitude": Decimal("19.1136"),
                "longitude": Decimal("72.8697"),
            },
            {
                "name": "Bandra East",
                "branch_type": Branch.BranchType.SUB,
                "address_line1": "Hill Road, Bandra East",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400051",
                "phone": "+91 98200 20002",
                "email": "bandra@fitnation.test",
                "latitude": Decimal("19.0596"),
                "longitude": Decimal("72.8295"),
            },
        ]
        branches = []
        for spec in branch_specs:
            branch, created = Branch.objects.get_or_create(
                tenant=tenant,
                name=spec["name"],
                defaults={
                    "branch_type": spec["branch_type"],
                    "address_line1": spec["address_line1"],
                    "city": spec["city"],
                    "state": spec["state"],
                    "postal_code": spec["postal_code"],
                    "country": "India",
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "phone": spec["phone"],
                    "email": spec["email"],
                    "opening_time": time(5, 0),
                    "closing_time": time(23, 0),
                    "operating_days": [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ],
                    "is_active": True,
                    "is_headquarters": False,
                },
            )
            branches.append(branch)
            self._report(f"Branch {spec['name']}", created)
        return branches

    # ─── 4. Trainer profiles ──────────────────────────────────────────────
    def _seed_trainer_profiles(self, staff):
        trainer_specs = [
            {
                "user": staff[User.Role.TRAINER],
                "specialization": "Strength & Conditioning",
                "bio": "Certified strength coach with 8 years of experience helping clients build functional strength.",
                "certifications": [
                    {"name": "ACE Certified Personal Trainer", "issuer": "ACE", "year": 2018, "expiry": "2026-12-31"},
                    {"name": "NSCA CSCS", "issuer": "NSCA", "year": 2020, "expiry": "2027-06-30"},
                ],
                "experience_years": 8,
                "rating": Decimal("4.80"),
                "max_clients": 40,
            },
            {
                "user": staff[User.Role.TRAINER],
                "specialization": "Weight Loss & HIIT",
                "bio": "Specialist in high-intensity interval training and sustainable weight-loss programs.",
                "certifications": [
                    {"name": "ISSA Certified Fitness Trainer", "issuer": "ISSA", "year": 2019, "expiry": "2026-09-30"},
                ],
                "experience_years": 6,
                "rating": Decimal("4.60"),
                "max_clients": 35,
            },
            {
                "user": staff[User.Role.TRAINER],
                "specialization": "Yoga & Mobility",
                "bio": "Yoga instructor and mobility specialist focused on flexibility and injury prevention.",
                "certifications": [
                    {"name": "RYT-200 Yoga Teacher", "issuer": "Yoga Alliance", "year": 2017, "expiry": "2026-12-31"},
                    {"name": "Functional Range Conditioning", "issuer": "FRC", "year": 2021, "expiry": "2027-03-31"},
                ],
                "experience_years": 7,
                "rating": Decimal("4.90"),
                "max_clients": 30,
            },
        ]
        trainers = []
        for spec in trainer_specs:
            trainer, created = Trainer.objects.get_or_create(
                user=spec["user"],
                defaults={
                    "specialization": spec["specialization"],
                    "bio": spec["bio"],
                    "certifications": spec["certifications"],
                    "experience_years": spec["experience_years"],
                    "rating": spec["rating"],
                    "max_clients": spec["max_clients"],
                    "is_active": True,
                },
            )
            trainers.append(trainer)
            self._report(f"Trainer profile {spec['user'].email}", created)
        return trainers

    # ─── 5. Trainer schedules ─────────────────────────────────────────────
    def _seed_trainer_schedules(self, tenant, trainers):
        # Each trainer works 5 days a week with a morning and/or evening slot.
        day_pool = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
        ]
        slots = [
            (time(6, 0), time(10, 0)),
            (time(17, 0), time(21, 0)),
        ]
        for idx, trainer in enumerate(trainers):
            # Rotate which days each trainer is off.
            off_day = day_pool[(idx * 2) % len(day_pool)]
            for day in day_pool:
                if day == off_day:
                    continue
                slot = slots[idx % len(slots)]
                schedule, created = TrainerSchedule.objects.get_or_create(
                    tenant=tenant,
                    trainer=trainer,
                    day_of_week=day,
                    defaults={
                        "start_time": slot[0],
                        "end_time": slot[1],
                        "is_available": True,
                    },
                )
                self._report(f"Schedule {trainer.user.email} {day}", created)

    # ─── 6. Customer profiles ─────────────────────────────────────────────
    def _seed_customer_profiles(self, tenant, customer_users, branches):
        profiles = []
        for i, user in enumerate(customer_users):
            gender = "male" if i % 2 == 1 else "female"
            age = RNG.randint(18, 55)
            dob = _today() - timedelta(days=age * 365 + RNG.randint(0, 300))
            branch = branches[i % len(branches)] if branches else None
            profile, created = Customer.objects.get_or_create(
                tenant=tenant,
                email=user.email,
                defaults={
                    "user": user,
                    "branch": branch,
                    "name": f"{user.first_name} {user.last_name}",
                    "phone": user.phone,
                    "date_of_birth": dob,
                    "gender": gender,
                    "emergency_contact_name": RNG.choice(_EMERGENCY_NAMES),
                    "emergency_contact_phone": f"+91 9{RNG.randint(100000000, 999999999)}",
                    "address_street": RNG.choice(_MUMBAI_STREETS),
                    "address_city": "Mumbai",
                    "address_state": "Maharashtra",
                    "address_postal_code": str(RNG.randint(400001, 400099)),
                    "status": Customer.Status.ACTIVE,
                    "is_active": True,
                },
            )
            profiles.append(profile)
            self._report(f"Customer profile {user.email}", created)
        return profiles

    # ─── 7. Health profiles ──────────────────────────────────────────────
    def _seed_health_profiles(self, tenant, customer_profiles):
        for profile in customer_profiles:
            gender = profile.gender
            if gender == "male":
                height = RNG.uniform(165, 185)
                weight = RNG.uniform(60, 95)
            else:
                height = RNG.uniform(152, 172)
                weight = RNG.uniform(48, 80)
            height = round(height, 2)
            weight = round(weight, 2)
            health, created = HealthProfile.objects.get_or_create(
                tenant=tenant,
                customer=profile,
                defaults={
                    "height_cm": Decimal(str(height)),
                    "weight_kg": Decimal(str(weight)),
                    "blood_group": RNG.choice(_BLOOD_GROUPS),
                    "current_injuries": [],
                    "past_injuries": RNG.choice([[], ["knee sprain"], ["shoulder strain"], []]),
                    "medical_conditions": RNG.choice([[], [], ["mild hypertension"], []]),
                    "allergies": [],
                    "food_allergies": RNG.choice([[], [], ["peanuts"], []]),
                    "medications": [],
                    "dietary_restrictions": RNG.choice([[], [], ["vegetarian"], []]),
                },
            )
            self._report(f"Health profile {profile.email}", created)

    # ─── 8. Fitness goals ────────────────────────────────────────────────
    def _seed_fitness_goals(self, tenant, customer_profiles):
        for profile in customer_profiles:
            num_goals = RNG.randint(1, 2)
            chosen = RNG.sample(_GOAL_TYPES, num_goals)
            for goal_type in chosen:
                lo, hi, unit = _GOAL_TARGETS[goal_type]
                target_val = round(RNG.uniform(lo, hi), 1)
                goal, created = FitnessGoal.objects.get_or_create(
                    tenant=tenant,
                    customer=profile,
                    goal_type=goal_type,
                    defaults={
                        "is_active": True,
                        "status": FitnessGoal.Status.ACTIVE,
                        "target_value": Decimal(str(target_val)),
                        "target_unit": unit,
                        "target_date": _today() + timedelta(days=RNG.randint(30, 180)),
                        "current_value": Decimal(str(round(target_val * RNG.uniform(0.1, 0.6), 1))),
                        "notes": f"Working towards {goal_type.replace('_', ' ')} goal.",
                    },
                )
                self._report(f"Fitness goal {profile.email} {goal_type}", created)

    # ─── 9. Membership plans ─────────────────────────────────────────────
    def _seed_membership_plans(self, tenant):
        plan_specs = [
            {
                "name": "Monthly Basic",
                "plan_type": MembershipPlan.PlanType.MONTHLY,
                "price": Decimal("1500.00"),
                "duration_days": 30,
                "description": "Access to gym floor and locker room for one month.",
            },
            {
                "name": "Monthly Premium",
                "plan_type": MembershipPlan.PlanType.MONTHLY,
                "price": Decimal("2500.00"),
                "duration_days": 30,
                "description": "Full gym access + group classes + sauna for one month.",
            },
            {
                "name": "Quarterly",
                "plan_type": MembershipPlan.PlanType.MONTHLY,
                "price": Decimal("4000.00"),
                "duration_days": 90,
                "description": "Three months of full gym access at a discounted rate.",
            },
            {
                "name": "Yearly",
                "plan_type": MembershipPlan.PlanType.YEARLY,
                "price": Decimal("12000.00"),
                "duration_days": 365,
                "description": "All-access annual membership with best value.",
            },
            {
                "name": "PT Package",
                "plan_type": MembershipPlan.PlanType.PT,
                "price": Decimal("8000.00"),
                "duration_days": 60,
                "description": "10 personal training sessions over 2 months.",
            },
        ]
        plans = {}
        for spec in plan_specs:
            plan, created = MembershipPlan.objects.get_or_create(
                tenant=tenant,
                name=spec["name"],
                defaults={
                    "plan_type": spec["plan_type"],
                    "price": spec["price"],
                    "duration_days": spec["duration_days"],
                    "description": spec["description"],
                    "is_active": True,
                },
            )
            plans[spec["name"]] = plan
            self._report(f"Membership plan {spec['name']}", created)
        return plans

    # ─── 10. Memberships ─────────────────────────────────────────────────
    def _seed_memberships(self, tenant, customer_profiles, plans):
        memberships = []
        plan_names = list(plans.keys())
        for i, profile in enumerate(customer_profiles):
            # 15 active, 3 expired, 2 cancelled
            if i < 15:
                status = Membership.Status.ACTIVE
                plan = plans[plan_names[i % len(plan_names)]]
                # Ensure end date is in the future for active memberships.
                end = _today() + timedelta(days=RNG.randint(10, plan.duration_days))
                start = end - timedelta(days=plan.duration_days)
            elif i < 18:
                status = Membership.Status.EXPIRED
                plan = plans[plan_names[i % len(plan_names)]]
                end = _today() - timedelta(days=RNG.randint(5, 30))
                start = end - timedelta(days=plan.duration_days)
            else:
                status = Membership.Status.CANCELLED
                plan = plans[plan_names[i % len(plan_names)]]
                end = _today() + timedelta(days=RNG.randint(10, 60))
                start = end - timedelta(days=plan.duration_days)

            membership, created = Membership.objects.get_or_create(
                tenant=tenant,
                customer=profile,
                plan=plan,
                start_date=start,
                end_date=end,
                defaults={
                    "status": status,
                    "auto_renew": status == Membership.Status.ACTIVE and RNG.random() < 0.5,
                },
            )
            memberships.append(membership)
            self._report(f"Membership {profile.email} ({status})", created)
        return memberships

    # ─── 11. Payments ─────────────────────────────────────────────────────
    def _seed_payments(self, tenant, customer_profiles, memberships):
        methods = ["cash", "upi", "card", "online"]
        for i, membership in enumerate(memberships):
            profile = membership.customer
            # Completed payment for the membership amount.
            payment, created = Payment.objects.get_or_create(
                tenant=tenant,
                customer=profile,
                membership=membership,
                transaction_id=f"TXN{i+1:06d}",
                defaults={
                    "amount": membership.plan.price,
                    "payment_method": methods[i % len(methods)],
                    "status": Payment.Status.COMPLETED,
                    "paid_at": _dt(RNG.randint(1, 60), RNG.randint(9, 20)),
                    "notes": f"Payment for {membership.plan.name}",
                },
            )
            self._report(f"Payment {profile.email} ({membership.plan.name})", created)

            # Occasionally add a second (pending/failed) payment for realism.
            if i % 5 == 0:
                extra_status = RNG.choice([Payment.Status.PENDING, Payment.Status.FAILED])
                Payment.objects.get_or_create(
                    tenant=tenant,
                    customer=profile,
                    membership=membership,
                    transaction_id=f"TXN{i+1:06d}X",
                    defaults={
                        "amount": membership.plan.price,
                        "payment_method": RNG.choice(methods),
                        "status": extra_status,
                        "paid_at": None,
                        "notes": f"Retry payment ({extra_status})",
                    },
                )

    # ─── 12. Trainer assignments ─────────────────────────────────────────
    def _seed_trainer_assignments(self, tenant, trainers, customer_profiles, branches):
        for i, profile in enumerate(customer_profiles):
            trainer = trainers[i % len(trainers)]
            branch = profile.branch or (branches[i % len(branches)] if branches else None)

            # Branch-scoped assignment (trainers.TrainerAssignment)
            TrainerAssignment.objects.get_or_create(
                tenant=tenant,
                trainer=trainer,
                customer=profile,
                defaults={
                    "branch": branch,
                    "is_active": True,
                },
            )

            # Direct assignment (users.TrainerCustomerAssignment)
            TrainerCustomerAssignment.objects.get_or_create(
                tenant=tenant,
                trainer=trainer,
                customer=profile,
                defaults={
                    "is_active": True,
                },
            )

            # Branch-trainer mapping
            if branch is not None:
                BranchTrainerAssignment.objects.get_or_create(
                    branch=branch,
                    trainer=trainer,
                    defaults={
                        "is_primary": i % 3 == 0,
                        "is_active": True,
                    },
                )
        self.stdout.write(self.style.SUCCESS("  ✓ Trainer assignments seeded."))

    # ─── 13. Exercise categories ─────────────────────────────────────────
    def _seed_exercise_categories(self, tenant):
        cat_specs = [
            {"name": "Strength", "slug": "strength", "description": "Resistance and weight training exercises."},
            {"name": "Cardio", "slug": "cardio", "description": "Cardiovascular endurance exercises."},
            {"name": "Flexibility", "slug": "flexibility", "description": "Stretching and mobility exercises."},
            {"name": "Sports", "slug": "sports", "description": "Sport-specific conditioning exercises."},
        ]
        categories = {}
        for spec in cat_specs:
            cat, created = ExerciseCategory.objects.get_or_create(
                tenant=tenant,
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                },
            )
            categories[spec["slug"]] = cat
            self._report(f"Exercise category {spec['name']}", created)
        return categories

    # ─── 14. Workout plans ───────────────────────────────────────────────
    def _seed_workout_plans(self, tenant, categories, staff):
        plan_specs = [
            {
                "name": "Beginner Full Body",
                "goal": WorkoutPlan.Goal.GENERAL_FITNESS,
                "difficulty": WorkoutPlan.Difficulty.BEGINNER,
                "duration_weeks": 4,
                "description": "A gentle full-body program to build foundational strength and confidence.",
            },
            {
                "name": "Weight Loss Blast",
                "goal": WorkoutPlan.Goal.WEIGHT_LOSS,
                "difficulty": WorkoutPlan.Difficulty.INTERMEDIATE,
                "duration_weeks": 6,
                "description": "High-energy circuit training to maximize calorie burn and boost metabolism.",
            },
            {
                "name": "Muscle Builder Pro",
                "goal": WorkoutPlan.Goal.HYPERTROPHY,
                "difficulty": WorkoutPlan.Difficulty.ADVANCED,
                "duration_weeks": 8,
                "description": "Progressive overload split for advanced muscle growth.",
            },
            {
                "name": "Strength Foundation",
                "goal": WorkoutPlan.Goal.STRENGTH,
                "difficulty": WorkoutPlan.Difficulty.INTERMEDIATE,
                "duration_weeks": 6,
                "description": "Compound-lift focused program to build raw strength.",
            },
        ]
        created_by = staff.get(User.Role.TRAINER) or staff.get(User.Role.MANAGER)
        plans = {}
        for spec in plan_specs:
            plan, created = WorkoutPlan.objects.get_or_create(
                tenant=tenant,
                name=spec["name"],
                defaults={
                    "goal": spec["goal"],
                    "difficulty": spec["difficulty"],
                    "duration_weeks": spec["duration_weeks"],
                    "description": spec["description"],
                    "is_template": True,
                    "created_by": created_by,
                },
            )
            plans[spec["name"]] = plan
            self._report(f"Workout plan {spec['name']}", created)
        return plans

    # ─── 15. Workout days & exercises ────────────────────────────────────
    def _seed_workout_days(self, tenant, workout_plans, categories):
        # Map plan name -> list of (day_number, focus, [exercise names])
        plan_days = {
            "Beginner Full Body": [
                (1, "Full Body A", ["Goblet Squat", "Push-Up", "Seated Cable Row", "Plank", "Dumbbell Bicep Curl"]),
                (
                    3,
                    "Full Body B",
                    ["Leg Press", "Dumbbell Shoulder Press", "Lat Pulldown", "Calf Raise", "Triceps Pushdown"],
                ),
                (5, "Cardio & Core", ["Treadmill Run", "Mountain Climbers", "Plank", "Jumping Jacks"]),
            ],
            "Weight Loss Blast": [
                (1, "HIIT Circuit", ["Burpees", "High Knees", "Jump Rope", "Kettlebell Swing", "Mountain Climbers"]),
                (
                    3,
                    "Strength + Cardio",
                    ["Barbell Back Squat", "Treadmill Run", "Dumbbell Chest Fly", "Rowing Machine"],
                ),
                (
                    5,
                    "Full Body Burn",
                    ["Deadlift", "Boxing Bag Workout", "Step-Up", "High-Intensity Interval Training"],
                ),
            ],
            "Muscle Builder Pro": [
                (
                    1,
                    "Push Day",
                    [
                        "Barbell Bench Press",
                        "Incline Dumbbell Press",
                        "Dumbbell Shoulder Press",
                        "Triceps Pushdown",
                        "Dumbbell Lateral Raise",
                    ],
                ),
                (2, "Pull Day", ["Deadlift", "Pull-Up", "Bent-Over Barbell Row", "Face Pull", "Dumbbell Bicep Curl"]),
                (4, "Leg Day", ["Barbell Back Squat", "Leg Press", "Romanian Deadlift", "Hip Thrust", "Calf Raise"]),
                (
                    6,
                    "Arms & Shoulders",
                    [
                        "Overhead Press",
                        "Dumbbell Lateral Raise",
                        "Dumbbell Bicep Curl",
                        "Triceps Pushdown",
                        "Face Pull",
                    ],
                ),
            ],
            "Strength Foundation": [
                (1, "Squat Focus", ["Barbell Back Squat", "Goblet Squat", "Leg Press", "Calf Raise", "Plank"]),
                (
                    3,
                    "Press Focus",
                    ["Overhead Press", "Barbell Bench Press", "Dumbbell Shoulder Press", "Triceps Pushdown"],
                ),
                (5, "Deadlift Focus", ["Deadlift", "Romanian Deadlift", "Bent-Over Barbell Row", "Face Pull", "Plank"]),
            ],
        }

        for plan_name, days in plan_days.items():
            plan = workout_plans[plan_name]
            for day_number, focus, exercise_names in days:
                day, created = WorkoutDay.objects.get_or_create(
                    tenant=tenant,
                    workout_plan=plan,
                    day_number=day_number,
                    defaults={
                        "focus": focus,
                    },
                )
                self._report(f"Workout day {plan_name} #{day_number}", created)

                for order, ex_name in enumerate(exercise_names):
                    exercise = Exercise.objects.filter(tenant=tenant, name=ex_name).first()
                    if exercise is None:
                        continue
                    WorkoutExercise.objects.get_or_create(
                        tenant=tenant,
                        workout_day=day,
                        exercise=exercise,
                        defaults={
                            "sets": RNG.randint(3, 5),
                            "reps": RNG.choice(["8-12", "10", "12-15", "5-8"]),
                            "rest_seconds": RNG.choice([45, 60, 90]),
                            "order": order,
                        },
                    )
        self.stdout.write(self.style.SUCCESS("  ✓ Workout days & exercises seeded."))

    # ─── 16. Customer workout assignments ────────────────────────────────
    def _seed_workout_assignments(self, tenant, customer_profiles, workout_plans, staff):
        plan_names = list(workout_plans.keys())
        assigned_by = staff.get(User.Role.TRAINER) or staff.get(User.Role.MANAGER)
        for i, profile in enumerate(customer_profiles):
            plan = workout_plans[plan_names[i % len(plan_names)]]
            start = _today() - timedelta(days=RNG.randint(5, 20))
            WorkoutAssignment.objects.get_or_create(
                tenant=tenant,
                customer=profile,
                workout_plan=plan,
                defaults={
                    "start_date": start,
                    "end_date": start + timedelta(days=plan.duration_weeks * 7),
                    "is_active": True,
                    "assigned_by": assigned_by,
                    "notes": f"Assigned {plan.name} for {plan.duration_weeks} weeks.",
                },
            )
        self.stdout.write(self.style.SUCCESS("  ✓ Customer workout assignments seeded."))

    # ─── 17. Diet plans ──────────────────────────────────────────────────
    def _seed_diet_plans(self, tenant):
        diet_specs = [
            {
                "name": "Weight Loss Diet",
                "goal": DietPlan.Goal.CUT,
                "daily_calories": 1800,
                "protein_ratio": 35.0,
                "carb_ratio": 35.0,
                "fat_ratio": 30.0,
                "duration_days": 7,
                "description": "A calorie-controlled Indian diet for sustainable fat loss.",
            },
            {
                "name": "Muscle Gain Diet",
                "goal": DietPlan.Goal.BULK,
                "daily_calories": 2800,
                "protein_ratio": 30.0,
                "carb_ratio": 45.0,
                "fat_ratio": 25.0,
                "duration_days": 7,
                "description": "A high-protein, calorie-surplus diet to support muscle growth.",
            },
            {
                "name": "Balanced Maintenance",
                "goal": DietPlan.Goal.MAINTAIN,
                "daily_calories": 2200,
                "protein_ratio": 30.0,
                "carb_ratio": 40.0,
                "fat_ratio": 30.0,
                "duration_days": 7,
                "description": "A balanced Indian diet to maintain weight and energy levels.",
            },
        ]
        plans = {}
        for spec in diet_specs:
            plan, created = DietPlan.objects.get_or_create(
                tenant=tenant,
                name=spec["name"],
                defaults={
                    "goal": spec["goal"],
                    "daily_calories": spec["daily_calories"],
                    "protein_ratio": spec["protein_ratio"],
                    "carb_ratio": spec["carb_ratio"],
                    "fat_ratio": spec["fat_ratio"],
                    "duration_days": spec["duration_days"],
                    "description": spec["description"],
                    "is_template": True,
                },
            )
            plans[spec["name"]] = plan
            self._report(f"Diet plan {spec['name']}", created)

        # Build days + meals for each plan.
        self._seed_diet_days(tenant, plans)
        return plans

    def _seed_diet_days(self, tenant, diet_plans):
        # meal_type -> list of (food_name, quantity)
        meal_menus = {
            "breakfast": [
                ("Oats (rolled)", 1.0),
                ("Milk (toned, 3% fat)", 1.0),
                ("Banana", 1.0),
            ],
            "morning_snack": [
                ("Almonds", 0.5),
                ("Apple", 1.0),
            ],
            "lunch": [
                ("Roti (wheat chapati)", 2.0),
                ("Chana Dal (cooked)", 1.0),
                ("Curd (dahi)", 1.0),
                ("Spinach (palak)", 1.0),
            ],
            "evening_snack": [
                ("Roasted Chana", 1.0),
                ("Green Tea (unsweetened)", 1.0),
            ],
            "dinner": [
                ("Brown Rice (cooked)", 1.0),
                ("Chicken Breast (cooked)", 1.0),
                ("Broccoli", 1.0),
                ("Cucumber", 1.0),
            ],
        }
        for plan_name, plan in diet_plans.items():
            for day_number in range(1, 8):
                day, created = DietDay.objects.get_or_create(
                    tenant=tenant,
                    diet_plan=plan,
                    day_number=day_number,
                    defaults={"notes": f"Day {day_number} of {plan.name}."},
                )
                self._report(f"Diet day {plan_name} #{day_number}", created)

                for meal_type, items in meal_menus.items():
                    for food_name, qty in items:
                        food = FoodItem.objects.filter(name=food_name).first()
                        if food is None:
                            continue
                        DietMeal.objects.get_or_create(
                            tenant=tenant,
                            diet_day=day,
                            meal_type=meal_type,
                            food_item=food,
                            defaults={"quantity": qty},
                        )
        self.stdout.write(self.style.SUCCESS("  ✓ Diet days & meals seeded."))

    # ─── 18. Diet assignments ─────────────────────────────────────────────
    def _seed_diet_assignments(self, tenant, customer_profiles, diet_plans, staff):
        plan_names = list(diet_plans.keys())
        assigned_by = staff.get(User.Role.DIETITIAN) or staff.get(User.Role.MANAGER)
        for i, profile in enumerate(customer_profiles):
            plan = diet_plans[plan_names[i % len(plan_names)]]
            start = _today() - timedelta(days=RNG.randint(5, 20))
            DietAssignment.objects.get_or_create(
                tenant=tenant,
                customer=profile,
                diet_plan=plan,
                defaults={
                    "start_date": start,
                    "end_date": start + timedelta(days=plan.duration_days),
                    "is_active": True,
                    "assigned_by": assigned_by,
                    "notes": f"Following {plan.name}.",
                },
            )
        self.stdout.write(self.style.SUCCESS("  ✓ Diet assignments seeded."))

    # ─── 19. Attendance records ───────────────────────────────────────────
    def _seed_attendance(self, tenant, customer_profiles, branches):
        all_branches = list(Branch.objects.filter(tenant=tenant))
        if not all_branches:
            all_branches = branches
        methods = ["qr", "mobile", "manual"]
        for profile in customer_profiles:
            # Each customer visits 8-20 times over the past 30 days.
            num_visits = RNG.randint(8, 20)
            visit_days = RNG.sample(range(1, 31), num_visits)
            for days_ago in visit_days:
                branch = profile.branch or RNG.choice(all_branches)
                check_in = _dt(days_ago, RNG.randint(6, 20), RNG.randint(0, 59))
                check_out = check_in + timedelta(minutes=RNG.randint(45, 120))
                AttendanceRecord.objects.get_or_create(
                    tenant=tenant,
                    customer=profile,
                    branch=branch,
                    check_in_time=check_in,
                    defaults={
                        "check_out_time": check_out,
                        "method": RNG.choice(methods),
                        "date": check_in.date(),
                    },
                )
        self.stdout.write(self.style.SUCCESS("  ✓ Attendance records seeded."))

    # ─── 20. Feedback ─────────────────────────────────────────────────────
    def _seed_feedback(self, tenant, customer_profiles, staff):
        categories = ["workout", "diet", "trainer", "facility", "app"]
        manager = staff.get(User.Role.MANAGER)
        num_entries = RNG.randint(10, 15)
        sample = RNG.sample(customer_profiles, min(num_entries, len(customer_profiles)))
        for i, profile in enumerate(sample):
            rating = RNG.randint(3, 5)
            category = categories[i % len(categories)]
            comment = _FEEDBACK_COMMENTS[i % len(_FEEDBACK_COMMENTS)]
            feedback, created = Feedback.objects.get_or_create(
                tenant=tenant,
                customer=profile,
                category=category,
                rating=rating,
                comment=comment,
                defaults={
                    "is_anonymous": RNG.random() < 0.2,
                    "response": (
                        "Thank you for your feedback! We appreciate it."
                        if rating >= 4
                        else "We're sorry to hear that. We'll work on improving."
                    ),
                    "response_by": manager,
                    "response_at": _dt(RNG.randint(1, 5)),
                },
            )
            self._report(f"Feedback {profile.email} ({rating}/5)", created)

    # ─── Helpers ─────────────────────────────────────────────────────────
    def _report(self, label, created):
        if created:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {label}"))
        else:
            self.stdout.write(self.style.WARNING(f"  - Skipped (exists): {label}"))
