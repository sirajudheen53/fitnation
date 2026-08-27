"""
Seed rich linked dummy data for FitNation local development.

Usage::

    python manage.py seed_dummy_data [--reset]

Creates:
    - Staff users (gym owner, manager, trainer, dietitian)
    - 5 realistic customers with full linked profiles
    - Branch with amenities
    - Membership plans (Monthly, 6-Month, Yearly, PT)
    - Active memberships for all customers
    - Payments across cash, UPI, card
    - Attendance records for past 14 days
    - Workout plans (Push/Pull/Legs + Full Body) with days → exercises
    - Diet plans (Weight Loss + Muscle Gain) with days → meals
    - Workout & diet assignments for all customers
"""

import random
from datetime import date, datetime, timedelta
from datetime import timezone as dt_tz
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.branches.models import Branch, BranchAmenity
from apps.customers.models import (
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
)
from apps.diet.models import DietAssignment, DietDay, DietMeal, DietPlan, FoodItem
from apps.exercises.models import Exercise, ExerciseCategory
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.payments.models import Payment
from apps.tenants.models import Tenant, TenantSettings
from apps.users.models import User
from apps.workouts.models import WorkoutAssignment, WorkoutDay, WorkoutExercise, WorkoutPlan

# ─── Helpers ────────────────────────────────────────────────────────────────


def pk(obj):
    return obj.pk


# ─── Seed Data ──────────────────────────────────────────────────────────────

_USERS = [
    {
        "email": "owner@fitnation.test",
        "first_name": "Rajesh",
        "last_name": "Mehta",
        "role": "gym_owner",
        "is_owner": True,
        "password": "FitLocal!23",
    },
    {
        "email": "manager@fitnation.test",
        "first_name": "Priya",
        "last_name": "Sharma",
        "role": "manager",
        "is_owner": False,
        "password": "FitLocal!23",
    },
    {
        "email": "trainer@fitnation.test",
        "first_name": "Arjun",
        "last_name": "Singh",
        "role": "trainer",
        "is_owner": False,
        "password": "FitLocal!23",
    },
    {
        "email": "dietitian@fitnation.test",
        "first_name": "Neha",
        "last_name": "Patel",
        "role": "dietitian",
        "is_owner": False,
        "password": "FitLocal!23",
    },
]

_CUSTOMERS = [
    {
        "email": "rahul.sharma@fitnation.test",
        "first_name": "Rahul",
        "last_name": "Sharma",
        "phone": "+91 98765 43210",
        "date_of_birth": date(1995, 3, 15),
        "gender": "male",
        "emergency_contact_name": "Vikram Sharma",
        "emergency_contact_phone": "+91 98765 43211",
        "address_city": "Mumbai",
        "address_state": "Maharashtra",
        "profile_photo": "",
    },
    {
        "email": "priya.patel@fitnation.test",
        "first_name": "Priya",
        "last_name": "Patel",
        "phone": "+91 98765 43220",
        "date_of_birth": date(1998, 7, 22),
        "gender": "female",
        "emergency_contact_name": "Meena Patel",
        "emergency_contact_phone": "+91 98765 43221",
        "address_city": "Mumbai",
        "address_state": "Maharashtra",
    },
    {
        "email": "amit.joshi@fitnation.test",
        "first_name": "Amit",
        "last_name": "Joshi",
        "phone": "+91 98765 43230",
        "date_of_birth": date(1990, 11, 8),
        "gender": "male",
        "emergency_contact_name": "Sunita Joshi",
        "emergency_contact_phone": "+91 98765 43231",
        "address_city": "Mumbai",
        "address_state": "Maharashtra",
    },
    {
        "email": "sneha.iyengar@fitnation.test",
        "first_name": "Sneha",
        "last_name": "Iyengar",
        "phone": "+91 98765 43240",
        "date_of_birth": date(1993, 5, 30),
        "gender": "female",
        "emergency_contact_name": "Lakshmi Iyengar",
        "emergency_contact_phone": "+91 98765 43241",
        "address_city": "Mumbai",
        "address_state": "Maharashtra",
    },
    {
        "email": "vikram.nair@fitnation.test",
        "first_name": "Vikram",
        "last_name": "Nair",
        "phone": "+91 98765 43250",
        "date_of_birth": date(1988, 9, 12),
        "gender": "male",
        "emergency_contact_name": "Geeta Nair",
        "emergency_contact_phone": "+91 98765 43251",
        "address_city": "Mumbai",
        "address_state": "Maharashtra",
    },
]

_MEMBERSHIP_PLANS = [
    {
        "name": "Monthly Basic",
        "plan_type": "monthly",
        "price": Decimal("1499"),
        "duration_days": 30,
        "description": "Access to gym floor and locker room.",
    },
    {
        "name": "6-Month Premium",
        "plan_type": "monthly",
        "price": Decimal("7999"),
        "duration_days": 180,
        "description": "Full gym access + group classes for 6 months.",
    },
    {
        "name": "Annual Pro",
        "plan_type": "yearly",
        "price": Decimal("14999"),
        "duration_days": 365,
        "description": "All-access annual membership with personal training sessions.",
    },
    {
        "name": "PT - 12 Sessions",
        "plan_type": "pt",
        "price": Decimal("6000"),
        "duration_days": 60,
        "description": "12 personal training sessions over 2 months.",
    },
]

_MEMBERSHIP_CHOICES = ["Monthly Basic", "6-Month Premium", "Annual Pro", "PT - 12 Sessions"]

_ATTENDANCE_DAYS = 14

_AMENITIES = [
    "Free Weights Area",
    "Cardio Zone",
    "Group Fitness Studio",
    "Personal Training Zone",
    "Sauna",
    "Locker Rooms",
    "Juice Bar",
    "Parking",
]

_PAYMENT_METHODS = ["cash", "upi", "card"]
_PAYMENT_STATUSES = ["completed", "pending", "failed"]

_WORKOUT_PLANS = [
    {
        "name": "Push Pull Legs",
        "goal": "strength",
        "difficulty": "intermediate",
        "duration_weeks": 6,
        "days": [
            {
                "day_number": 1,
                "focus": "Push Day",
                "exercises": [
                    ("Barbell Bench Press", 4, "8-10"),
                    ("Dumbbell Shoulder Press", 3, "10-12"),
                    ("Incline Dumbbell Press", 3, "10-12"),
                    ("Triceps Pushdown", 3, "12-15"),
                    ("Dumbbell Lateral Raise", 3, "12-15"),
                ],
            },
            {
                "day_number": 2,
                "focus": "Pull Day",
                "exercises": [
                    ("Deadlift", 4, "5"),
                    ("Bent-Over Barbell Row", 4, "8-10"),
                    ("Lat Pulldown", 3, "10-12"),
                    ("Seated Cable Row", 3, "10-12"),
                    ("Face Pull", 3, "15"),
                    ("Dumbbell Bicep Curl", 3, "12"),
                ],
            },
            {
                "day_number": 3,
                "focus": "Leg Day",
                "exercises": [
                    ("Barbell Back Squat", 4, "8-10"),
                    ("Romanian Deadlift", 3, "10"),
                    ("Leg Press", 3, "12"),
                    ("Step-Up", 3, "10 each"),
                    ("Calf Raise", 4, "15"),
                ],
            },
        ],
    },
    {
        "name": "Full Body Strength",
        "goal": "hypertrophy",
        "difficulty": "beginner",
        "duration_weeks": 4,
        "days": [
            {
                "day_number": 1,
                "focus": "Full Body A",
                "exercises": [
                    ("Barbell Back Squat", 3, "10"),
                    ("Dumbbell Chest Fly", 3, "12"),
                    ("Seated Cable Row", 3, "12"),
                    ("Goblet Squat", 3, "12"),
                    ("Plank", 3, "45 sec"),
                ],
            },
            {
                "day_number": 2,
                "focus": "Full Body B",
                "exercises": [
                    ("Barbell Bench Press", 3, "10"),
                    ("Lat Pulldown", 3, "12"),
                    ("Romanian Deadlift", 3, "10"),
                    ("Dumbbell Shoulder Press", 3, "12"),
                    ("Hip Thrust", 3, "12"),
                ],
            },
        ],
    },
    {
        "name": "Weight Loss Cardio",
        "goal": "weight_loss",
        "difficulty": "beginner",
        "duration_weeks": 8,
        "days": [
            {
                "day_number": 1,
                "focus": "Cardio + Core",
                "exercises": [
                    ("Treadmill Run", 1, "20 min"),
                    ("Kettlebell Swing", 3, "15"),
                    ("Mountain Climbers", 3, "20"),
                    ("Plank", 3, "30 sec"),
                    ("High Knees", 3, "30 sec"),
                ],
            },
            {
                "day_number": 2,
                "focus": "Circuit Training",
                "exercises": [
                    ("Burpees", 3, "10"),
                    ("Jump Rope", 3, "3 min"),
                    ("Push-Up", 3, "10"),
                    ("Goblet Squat", 3, "12"),
                    ("Mountain Climbers", 3, "20"),
                ],
            },
        ],
    },
]

_DIET_PLANS = [
    {
        "name": "High Protein Weight Loss",
        "goal": "cut",
        "daily_calories": 1800,
        "protein_ratio": 40.0,
        "carb_ratio": 35.0,
        "fat_ratio": 25.0,
        "duration_days": 30,
        "days": [
            {
                "day_number": 1,
                "meals": [
                    ("Scrambled Eggs (3)", 2, "breakfast"),
                    ("Chicken Breast (100g)", 1, "lunch"),
                    ("Boiled Chickpeas", 1, "evening_snack"),
                    ("Grilled Fish (150g)", 1, "dinner"),
                ],
            },
            {
                "day_number": 2,
                "meals": [
                    ("Oats (cooked)", 1.5, "breakfast"),
                    ("Paneer (100g)", 1, "lunch"),
                    ("Almonds", 0.5, "evening_snack"),
                    ("Chicken Curry (150g)", 1, "dinner"),
                ],
            },
        ],
    },
    {
        "name": "Muscle Gain Diet",
        "goal": "bulk",
        "daily_calories": 2800,
        "protein_ratio": 30.0,
        "carb_ratio": 45.0,
        "fat_ratio": 25.0,
        "duration_days": 30,
        "days": [
            {
                "day_number": 1,
                "meals": [
                    ("Oats (cooked)", 2, "breakfast"),
                    ("Brown Rice (150g)", 1.5, "lunch"),
                    ("Banana Shake", 1, "morning_snack"),
                    ("Chicken Breast (150g)", 1.5, "dinner"),
                    ("Sweet Potato (200g)", 1, "dinner"),
                ],
            },
            {
                "day_number": 2,
                "meals": [
                    ("Scrambled Eggs (4)", 2, "breakfast"),
                    ("Brown Rice (150g)", 1.5, "lunch"),
                    ("Peanut Butter", 1, "morning_snack"),
                    ("Grilled Fish (150g)", 1.5, "dinner"),
                    ("Makhana (fox nuts)", 1, "evening_snack"),
                ],
            },
        ],
    },
]


# ─── Command ────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Seed rich linked dummy data for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all dummy customers, staff, memberships, payments, workouts, diets before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tenant = Tenant.objects.order_by("id").first()
        if not tenant:
            tenant = Tenant.objects.create(
                name="FitNation Test Gym",
                contact_email="admin@fitnation.test",
                status="active",
                subscription_plan="professional",
            )
            TenantSettings.objects.create(tenant=tenant, max_branches=3)
            self.stdout.write(f"Created tenant: {tenant.name}")

        # ── Reset if requested ────────────────────────────────────────────────
        if options["reset"]:
            self._reset(tenant)
            self.stdout.write(self.style.WARNING("Reset complete. Re-seeding…"))

        # ── Seed staff users ───────────────────────────────────────────────────
        self._seed_staff(tenant)
        owner = User.objects.get(email="owner@fitnation.test")
        trainer = User.objects.get(email="trainer@fitnation.test")

        # ── Branch ────────────────────────────────────────────────────────────
        branch = self._seed_branch(tenant)

        # ── Membership Plans ──────────────────────────────────────────────────
        plans = self._seed_membership_plans(tenant)

        # ── Customers + health + fitness goals ───────────────────────────────
        customers = self._seed_customers(tenant, branch)

        # ── Memberships ──────────────────────────────────────────────────────
        self._seed_memberships(tenant, customers, plans)

        # ── Payments ──────────────────────────────────────────────────────────
        self._seed_payments(tenant, customers)

        # ── Attendance ───────────────────────────────────────────────────────
        self._seed_attendance(tenant, customers, branch)

        # ── Exercise categories (if not already seeded) ─────────────────────
        self._ensure_exercise_categories(tenant)

        # ── Workout Plans ────────────────────────────────────────────────────
        workout_plans = self._seed_workout_plans(tenant, owner)

        # ── Workout Assignments ──────────────────────────────────────────────
        self._seed_workout_assignments(tenant, customers, workout_plans, owner)

        # ── Food Items (if not already seeded) ───────────────────────────────
        self._ensure_food_items()

        # ── Diet Plans ────────────────────────────────────────────────────────
        diet_plans = self._seed_diet_plans(tenant)

        # ── Diet Assignments ──────────────────────────────────────────────────
        self._seed_diet_assignments(tenant, customers, diet_plans, trainer)

        self.stdout.write(self.style.SUCCESS("\n✅  Dummy data seeded successfully!"))
        self.stdout.write(f"   Staff users : {len(_USERS)}")
        self.stdout.write(f"   Customers   : {len(customers)}")
        self.stdout.write(f"   Plans       : {len(plans)} membership plans")
        self.stdout.write(f"   Workout plans: {len(workout_plans)}")
        self.stdout.write(f"   Diet plans   : {len(diet_plans)}")
        self.stdout.write("\n   Login:  owner@fitnation.test / FitLocal!23")

    # ─── Individual seeders ──────────────────────────────────────────────────

    def _reset(self, tenant):
        """Delete all seeded data (anything with email containing @fitnation.test EXCEPT admin)."""
        seeded_emails = [u["email"] for u in _USERS] + [c["email"] for c in _CUSTOMERS]

        for email in seeded_emails:
            try:
                user = User.objects.get(email=email)
                # Delete customer if exists (cascades to health_profile, fitness_goals, memberships, payments, etc.)
                if hasattr(user, "customer_profile"):
                    customer = user.customer_profile
                    # Delete all related data
                    FitnessGoal.objects.filter(customer=customer).delete()
                    HealthProfile.objects.filter(customer=customer).delete()
                    BodyMeasurement.objects.filter(customer=customer).delete()
                    WorkoutAssignment.objects.filter(customer=customer).delete()
                    DietAssignment.objects.filter(customer=customer).delete()
                    Payment.objects.filter(customer=customer).delete()
                    Membership.objects.filter(customer=customer).delete()
                    customer.delete()
                user.delete()
                self.stdout.write(f"  Deleted user: {email}")
            except User.DoesNotExist:
                pass

        # Clean up plans and coupons
        WorkoutAssignment.objects.filter(tenant=tenant).delete()
        DietAssignment.objects.filter(tenant=tenant).delete()
        WorkoutPlan.objects.filter(tenant=tenant).delete()
        DietPlan.objects.filter(tenant=tenant).delete()
        MembershipPlan.objects.filter(tenant=tenant).delete()
        Coupon.objects.filter(tenant=tenant).delete()
        Branch.objects.filter(tenant=tenant).delete()
        self.stdout.write("  Reset complete.")

    def _seed_staff(self, tenant):
        created = []
        for data in _USERS:
            user, created_flag = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "tenant": tenant,
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "role": data["role"],
                    "is_owner": data["is_owner"],
                },
            )
            if created_flag:
                user.set_password(data["password"])
                user.save()
            created.append(user)
            status = "✅ created" if created_flag else "ℹ️  already exists"
            self.stdout.write(f"  {status}: {data['email']} ({data['role']})")
        return created

    def _seed_branch(self, tenant):
        branch, created = Branch.objects.get_or_create(
            tenant=tenant,
            name="FitNation Main Gym",
            defaults={
                "address_line1": "42 Fitness Road, Andheri West",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400053",
                "country": "India",
                "phone": "+91 22 2635 1234",
                "email": "mumbai@fitnation.test",
                "is_headquarters": True,
                "opening_time": "05:00",
                "closing_time": "23:00",
                "operating_days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            },
        )
        if created:
            for name in _AMENITIES:
                BranchAmenity.objects.create(branch=branch, name=name, is_available=True)
            self.stdout.write(f"  ✅ Created branch: {branch.name}")
        else:
            self.stdout.write(f"  ℹ️  Branch already exists: {branch.name}")
        return branch

    def _seed_membership_plans(self, tenant):
        plans = []
        for data in _MEMBERSHIP_PLANS:
            plan, created = MembershipPlan.objects.get_or_create(
                tenant=tenant,
                name=data["name"],
                defaults={
                    "plan_type": data["plan_type"],
                    "price": data["price"],
                    "duration_days": data["duration_days"],
                    "description": data["description"],
                },
            )
            plans.append(plan)
        self.stdout.write(f"  ✅ Seeded {len(plans)} membership plans")
        return plans

    def _seed_customers(self, tenant, branch):
        customers = []
        today = date.today()
        for i, data in enumerate(_CUSTOMERS):
            name = f"{data['first_name']} {data['last_name']}"
            user, user_created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "tenant": tenant,
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "role": "customer",
                },
            )
            if user_created:
                user.set_password("FitLocal!23")
                user.save()

            customer, cust_created = Customer.objects.get_or_create(
                tenant=tenant,
                email=data["email"],
                defaults={
                    "user": user,
                    "name": name,
                    "phone": data["phone"],
                    "branch": branch,
                    "date_of_birth": data["date_of_birth"],
                    "gender": data["gender"],
                    "emergency_contact_name": data["emergency_contact_name"],
                    "emergency_contact_phone": data["emergency_contact_phone"],
                    "address_city": data["address_city"],
                    "address_state": data["address_state"],
                    "status": "active",
                },
            )
            customers.append(customer)

            if cust_created:
                # Health profile
                heights = [175.0, 162.0, 178.0, 158.0, 180.0]
                weights = [78.0, 62.0, 85.0, 60.0, 90.0]
                HealthProfile.objects.create(
                    tenant=tenant,
                    customer=customer,
                    height_cm=Decimal(str(heights[i])),
                    weight_kg=Decimal(str(weights[i])),
                    blood_group=random.choice(["A+", "B+", "O+", "AB+", "A-"]),
                    injuries="",
                    current_injuries=[],
                    past_injuries=[],
                    medical_info={},
                    medical_conditions=[],
                    allergies=[],
                    food_allergies=["Dust"] if i == 0 else [],
                    medications=[],
                    dietary_restrictions=[],
                )

                # Body measurements (past 4 weeks)
                for week in range(4, 0, -1):
                    m_date = today - timedelta(weeks=week)
                    weight = weights[i] + random.uniform(-0.5, 0.5)
                    BodyMeasurement.objects.create(
                        tenant=tenant,
                        customer=customer,
                        date_logged=m_date,
                        weight_kg=Decimal(str(round(weight, 1))),
                        height_cm=Decimal(str(heights[i])),
                        chest_cm=Decimal(str(heights[i] * 0.52)),
                        waist_cm=Decimal(str(heights[i] * 0.45)),
                        biceps_cm=Decimal(str(14 + random.randint(0, 4))),
                        body_fat_percentage=Decimal(str(round(random.uniform(15, 25), 1))),
                    )

                # Fitness goal
                goal_types = ["lose_weight", "build_muscle", "general_fitness", "weight_loss", "strength"]
                FitnessGoal.objects.create(
                    tenant=tenant,
                    customer=customer,
                    goal_type=goal_types[i],
                    target_value=Decimal(str(random.randint(65, 80))),
                    target_unit="kg",
                    target_date=today + timedelta(days=90),
                    current_value=Decimal(str(weights[i])),
                    status="active",
                )

        self.stdout.write(f"  ✅ Seeded {len(customers)} customers with profiles")
        return customers

    def _seed_memberships(self, tenant, customers, plans):
        today = date.today()
        plan_by_name = {p.name: p for p in plans}
        for customer in customers:
            # Give each customer an active membership
            plan_name = random.choice(_MEMBERSHIP_CHOICES)
            plan = plan_by_name.get(plan_name)
            if not plan:
                continue
            start = today - timedelta(days=random.randint(1, 60))
            end = start + timedelta(days=plan.duration_days)
            status = "active" if end >= today else "expired"
            Membership.objects.get_or_create(
                tenant=tenant,
                customer=customer,
                plan=plan,
                defaults={
                    "start_date": start,
                    "end_date": end,
                    "status": status,
                    "auto_renew": random.choice([True, False]),
                },
            )
        self.stdout.write(f"  ✅ Seeded memberships for {len(customers)} customers")

    def _seed_payments(self, tenant, customers):
        today = date.today()
        methods = _PAYMENT_METHODS
        for customer in customers:
            membership = customer.memberships.order_by("-id").first()
            for p in range(random.randint(1, 3)):
                p_date = today - timedelta(days=random.randint(0, 30))
                p_date_tz = datetime(p_date.year, p_date.month, p_date.day, 10 + p, 0, 0, tzinfo=dt_tz.utc)
                method = random.choice(methods)
                Payment.objects.get_or_create(
                    tenant=tenant,
                    customer=customer,
                    membership=membership,
                    defaults={
                        "amount": Decimal(str(random.choice([999, 1499, 1999, 4999, 7999]))),
                        "payment_method": method,
                        "status": "completed",
                        "paid_at": p_date_tz,
                        "transaction_id": f"LOCAL-TXN-{p_date.strftime('%Y%m%d')}-{customer.id:03d}-{p}",
                        "notes": f"Payment for {membership.plan.name if membership else 'membership'}",
                    },
                )
        self.stdout.write(f"  ✅ Seeded payments for {len(customers)} customers")

    def _seed_attendance(self, tenant, customers, branch):
        today = date.today()
        for customer in customers:
            for days_ago in range(1, _ATTENDANCE_DAYS + 1):
                if random.random() < 0.7:  # 70% attendance rate
                    att_date = today - timedelta(days=days_ago)
                    check_in = datetime.combine(att_date, datetime.min.time().replace(hour=7 + random.randint(0, 2)))
                    check_out = check_in + timedelta(hours=random.randint(1, 2))
                    from apps.attendance.models import AttendanceRecord

                    AttendanceRecord.objects.get_or_create(
                        tenant=tenant,
                        customer=customer,
                        date=att_date,
                        defaults={
                            "branch": branch,
                            "check_in_time": check_in,
                            "check_out_time": check_out,
                            "method": random.choice(["manual", "qr", "mobile"]),
                        },
                    )
        self.stdout.write(f"  ✅ Seeded attendance for past {_ATTENDANCE_DAYS} days")

    def _ensure_exercise_categories(self, tenant):
        cats = {
            "strength": "Strength",
            "cardio": "Cardio",
            "flexibility": "Flexibility",
            "mobility": "Mobility",
        }
        for slug, name in cats.items():
            ExerciseCategory.objects.get_or_create(
                tenant=tenant,
                slug=slug,
                defaults={"name": name},
            )
        self.stdout.write(f"  ℹ️  Exercise categories: {ExerciseCategory.objects.filter(tenant=tenant).count()}")

    def _seed_workout_plans(self, tenant, owner):
        plans = []
        exercises = {e.name: e for e in Exercise.objects.filter(tenant=tenant)}

        for plan_data in _WORKOUT_PLANS:
            plan, created = WorkoutPlan.objects.get_or_create(
                tenant=tenant,
                name=plan_data["name"],
                defaults={
                    "goal": plan_data["goal"],
                    "difficulty": plan_data["difficulty"],
                    "duration_weeks": plan_data["duration_weeks"],
                    "created_by": owner,
                },
            )
            if created:
                for day_data in plan_data["days"]:
                    day, _ = WorkoutDay.objects.get_or_create(
                        tenant=tenant,
                        workout_plan=plan,
                        day_number=day_data["day_number"],
                        defaults={"focus": day_data["focus"]},
                    )
                    for order, (ex_name, sets, reps) in enumerate(day_data["exercises"]):
                        exercise = exercises.get(ex_name)
                        if exercise:
                            WorkoutExercise.objects.create(
                                tenant=tenant,
                                workout_day=day,
                                exercise=exercise,
                                sets=sets,
                                reps=str(reps),
                                rest_seconds=60,
                                order=order,
                            )
            plans.append(plan)

        self.stdout.write(f"  ✅ Seeded {len(plans)} workout plans")
        return plans

    def _seed_workout_assignments(self, tenant, customers, workout_plans, owner):
        today = date.today()
        from apps.workouts.models import WorkoutAssignment

        for customer in customers:
            if random.random() < 0.8:  # 80% have workout plans
                plan = random.choice(workout_plans)
                start = today - timedelta(days=random.randint(1, 14))
                end = start + timedelta(days=plan.duration_weeks * 7)
                WorkoutAssignment.objects.get_or_create(
                    tenant=tenant,
                    customer=customer,
                    workout_plan=plan,
                    defaults={
                        "start_date": start,
                        "end_date": end,
                        "is_active": True,
                        "assigned_by": owner,
                    },
                )
        self.stdout.write("  ✅ Seeded workout assignments")

    def _ensure_food_items(self):
        count = FoodItem.objects.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("  ⚠️  No food items found. Run: python manage.py seed_food_items"))
        else:
            self.stdout.write(f"  ℹ️  Food items catalog: {count} items")

    def _seed_diet_plans(self, tenant):
        plans = []
        food_items = {f.name: f for f in FoodItem.objects.all()}

        for plan_data in _DIET_PLANS:
            plan, created = DietPlan.objects.get_or_create(
                tenant=tenant,
                name=plan_data["name"],
                defaults={
                    "goal": plan_data["goal"],
                    "daily_calories": plan_data["daily_calories"],
                    "protein_ratio": plan_data["protein_ratio"],
                    "carb_ratio": plan_data["carb_ratio"],
                    "fat_ratio": plan_data["fat_ratio"],
                    "duration_days": plan_data["duration_days"],
                },
            )
            if created:
                for day_data in plan_data["days"]:
                    diet_day, _ = DietDay.objects.get_or_create(
                        tenant=tenant,
                        diet_plan=plan,
                        day_number=day_data["day_number"],
                    )
                    for meal_type, qty, meal_label in day_data["meals"]:
                        food = food_items.get(meal_type)
                        if food:
                            DietMeal.objects.create(
                                tenant=tenant,
                                diet_day=diet_day,
                                food_item=food,
                                quantity=qty,
                                meal_type=meal_label,
                            )
            plans.append(plan)

        self.stdout.write(f"  ✅ Seeded {len(plans)} diet plans")
        return plans

    def _seed_diet_assignments(self, tenant, customers, diet_plans, dietitian):
        today = date.today()
        for customer in customers:
            if random.random() < 0.8:
                plan = random.choice(diet_plans)
                start = today - timedelta(days=random.randint(1, 14))
                end = start + timedelta(days=plan.duration_days)
                DietAssignment.objects.get_or_create(
                    tenant=tenant,
                    customer=customer,
                    diet_plan=plan,
                    defaults={
                        "start_date": start,
                        "end_date": end,
                        "is_active": True,
                        "assigned_by": dietitian,
                    },
                )
        self.stdout.write("  ✅ Seeded diet assignments")
