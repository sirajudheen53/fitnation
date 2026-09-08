"""FitNation Test Gym (tenant 1) realistic data — port of QA ``seed_qa_data.py``.

``seed_staff`` runs on every ``seed_qa`` invocation (QA needs the staff logins);
``seed_realistic`` (customers, memberships/payments/invoices, diet, workouts,
operations, marketplace carts) runs with ``--realistic``.

Fixes vs original: plans/trainers/products are scoped to the tenant instead of
global ``objects.all()``, and missing catalogs no longer crash workout seeding.
"""

from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.customers.models import BodyMeasurement, Customer, FitnessGoal, HealthProfile
from apps.diet.models import DietDay, DietMeal, DietPlan, FoodItem
from apps.exercises.models import Exercise
from apps.feedback.models import Feedback
from apps.marketplace.models import Cart, CartItem, Product
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.payments.models import Invoice, Payment
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.users.models import Trainer
from apps.workouts.models import WorkoutAssignment, WorkoutDay, WorkoutExercise, WorkoutPlan

from .common import (
    PASSWORDS,
    ensure_demo_payments,
    ensure_trainer,
    ensure_trainer_schedule,
    ensure_user,
)

GOAL_POOL = [
    ("lose_weight", "Reduce body fat to 18%", 18.0, "%"),
    ("build_muscle", "Gain 5 kg lean muscle", 5.0, "kg"),
    ("endurance", "Run 10k under 60 min", 60.0, "min"),
    ("general_fitness", "Stay active and fit", 0, ""),
    ("flexibility", "Improve mobility", 0, ""),
]

CUSTOMERS = [
    ("Aarav", "Kulkarni", "aarav.k@gmail.com", "male", 178, 82),
    ("Sneha", "Deshpande", "sneha.d@gmail.com", "female", 162, 67),
    ("Vikram", "Rao", "vikram.rao@gmail.com", "male", 175, 90),
    ("Ishita", "Banerjee", "ishita.b@gmail.com", "female", 158, 54),
    ("Karan", "Mehta", "karan.mehta@gmail.com", "male", 180, 78),
    ("Divya", "Pillai", "divya.pillai@gmail.com", "female", 165, 60),
    ("Sanjay", "Gupta", "sanjay.gupta@gmail.com", "male", 170, 88),
    ("Riya", "Shah", "riya.shah@gmail.com", "female", 160, 52),
    ("Aditya", "Joshi", "aditya.joshi@gmail.com", "male", 182, 85),
    ("Neha", "Verma", "neha.verma@gmail.com", "female", 163, 70),
    ("Rahul", "Krishnan", "rahul.krish@gmail.com", "male", 174, 72),
    ("Pooja", "Khatri", "pooja.khatri@gmail.com", "female", 166, 58),
    ("Amit", "Chawla", "amit.chawla@gmail.com", "male", 168, 92),
    ("Swati", "Bhat", "swati.bhat@gmail.com", "female", 164, 71),
    ("Nikhil", "Gowda", "nikhil.gowda@gmail.com", "male", 178, 76),
    ("Lakshmi", "Menon", "lakshmi.menon@gmail.com", "female", 159, 66),
    ("Vivek", "Trivedi", "vivek.trivedi@gmail.com", "male", 176, 84),
    ("Ananya", "Sarkar", "ananya.sarkar@gmail.com", "female", 161, 50),
    ("Manoj", "Bhatt", "manoj.bhatt@gmail.com", "male", 169, 86),
    ("Tanvi", "Kulkarni", "tanvi.k@gmail.com", "female", 167, 58),
]


def seed_staff(tenant, reset_passwords: bool = True, echo=print) -> list[Trainer]:
    """Owner/manager/dietitian/4 trainers for the default tenant. Default run."""
    random.seed(42)
    password = PASSWORDS["tenant1_staff"]
    ensure_user(
        email="owner@fitnation.test",
        first_name="Rahul",
        last_name="Sharma",
        role="gym_owner",
        password=password,
        tenant=tenant,
        phone="+919812345670",
        reset_passwords=reset_passwords,
    )
    ensure_user(
        email="manager@fitnation.test",
        first_name="Priya",
        last_name="Nair",
        role="manager",
        password=password,
        tenant=tenant,
        phone="+919812345671",
        reset_passwords=reset_passwords,
    )
    ensure_user(
        email="dietitian@fitnation.test",
        first_name="Ananya",
        last_name="Iyer",
        role="dietitian",
        password=password,
        tenant=tenant,
        phone="+919812345672",
        reset_passwords=reset_passwords,
    )

    trainer_specs = [
        ("trainer1@fitnation.test", "Vikram", "Singh", "Strength & Conditioning", 7),
        ("trainer2@fitnation.test", "Meera", "Reddy", "HIIT & Functional", 5),
        ("trainer3@fitnation.test", "Arjun", "Patel", "Yoga & Mobility", 4),
        ("trainer4@fitnation.test", "Kavya", "Menon", "Bodybuilding", 6),
    ]
    trainers = []
    for email, fn, ln, spec, yrs in trainer_specs:
        user = ensure_user(
            email=email,
            first_name=fn,
            last_name=ln,
            role="trainer",
            password=password,
            tenant=tenant,
            phone=f"+9198{random.randint(10000000, 99999999)}",
            is_staff=False,
            reset_passwords=reset_passwords,
        )
        trainer = ensure_trainer(
            user,
            specialization=spec,
            bio=f"{fn} is a certified trainer with {yrs}+ years of experience in {spec}.",
            is_active=True,
            certifications=["ACE-CPT", "K11", "Precision Nutrition"],
            experience_years=yrs,
            rating=round(random.uniform(4.3, 4.9), 1),
            max_clients=15,
        )
        ensure_trainer_schedule(
            trainer,
            tenant,
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
            "06:00",
            "21:00",
        )
        trainers.append(trainer)
    echo("  tenant-1 staff: owner, manager, dietitian, 4 trainers")
    return trainers


def _seed_customers(tenant, branch) -> list[Customer]:
    created = []
    for name, lname, email, gender, hgt, wgt in CUSTOMERS:
        if Customer.objects.filter(email=email).exists():
            continue
        user = ensure_user(
            email=email,
            first_name=name,
            last_name=lname,
            role="customer",
            password=PASSWORDS["tenant1_customers"],
            tenant=tenant,
            phone=f"+91{random.randint(7000000000, 9999999999)}",
            is_staff=False,
        )
        customer = Customer.objects.create(
            tenant=tenant,
            user=user,
            branch=branch,
            name=f"{name} {lname}",
            email=email,
            phone=user.phone,
            gender=gender,
            date_of_birth=dt.date(1990 - random.randint(0, 18), random.randint(1, 12), random.randint(1, 28)),
            emergency_contact_name=f"Parent of {name}",
            emergency_contact_phone="+919900000000",
            address_street=(
                f"{random.randint(1, 300)}, "
                f"{random.choice(['MG Road', 'Linking Road', 'Banjara Hills', 'Indiranagar', 'Koramangala'])}"
            ),
            address_city=random.choice(["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Chennai"]),
            address_state=random.choice(["Karnataka", "Telangana", "Maharashtra", "Tamil Nadu"]),
            address_postal_code=str(random.randint(400001, 600010)),
            status=random.choice(["active", "active", "active", "inactive"]),
            notes="",
            is_active=True,
        )
        HealthProfile.objects.create(
            tenant=tenant,
            customer=customer,
            height_cm=hgt,
            weight_kg=wgt,
            bmi=round(wgt / (hgt / 100) ** 2, 1),
            blood_group=random.choice(["A+", "B+", "O+", "AB+", "O-"]),
            injuries="",
            current_injuries=[],
            past_injuries=[],
            medical_info={},
            medical_conditions=[],
            allergies=[],
            food_allergies=[],
            medications=[],
            dietary_restrictions=[],
        )
        goal_type, _notes, val, unit = random.choice(GOAL_POOL)
        FitnessGoal.objects.create(
            tenant=tenant,
            customer=customer,
            goal_type=goal_type,
            is_active=True,
            status="active",
            target_value=val,
            target_unit=unit,
            target_date=dt.date.today() + dt.timedelta(days=random.randint(60, 180)),
            current_value=0,
            notes="",
        )
        BodyMeasurement.objects.create(
            tenant=tenant,
            customer=customer,
            date_logged=dt.date.today(),
            weight_kg=wgt,
            height_cm=hgt,
            bmi=round(wgt / (hgt / 100) ** 2, 1),
            body_fat_percentage=round(random.uniform(15, 30), 1),
            chest_cm=round(random.uniform(88, 110), 1),
            waist_cm=round(random.uniform(70, 100), 1),
            hips_cm=round(random.uniform(88, 105), 1),
            biceps_cm=round(random.uniform(28, 38), 1),
            thighs_cm=round(random.uniform(50, 65), 1),
            neck_cm=round(random.uniform(34, 42), 1),
            notes="",
        )
        created.append(customer)
    return created


def _seed_plans(tenant, customers) -> None:
    plans = []
    plan_specs = [
        ("Basic Monthly", "monthly", 1500, 30, "Gym floor + cardio access"),
        ("Premium Yearly", "yearly", 12000, 365, "All access + steam + guest passes"),
        ("PT Combo", "pt", 6000, 30, "Monthly + 8 personal training sessions"),
        ("Student Monthly", "monthly", 1000, 30, "Student plan with valid ID"),
    ]
    for name, ptype, price, days, desc in plan_specs:
        plan, _ = MembershipPlan.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults=dict(plan_type=ptype, price=price, duration_days=days, description=desc, is_active=True),
        )
        plans.append(plan)

    Coupon.objects.get_or_create(
        tenant=tenant,
        code="FITNATION50",
        defaults=dict(
            discount_percent=10,
            max_uses=100,
            used_count=5,
            valid_from=dt.date.today() - dt.timedelta(days=30),
            valid_to=dt.date.today() + dt.timedelta(days=60),
            is_active=True,
        ),
    )

    for customer in customers:
        if Membership.objects.filter(customer=customer).exists():
            continue
        plan = random.choice(plans)
        start = dt.date.today() - dt.timedelta(days=random.randint(5, 200))
        end = start + dt.timedelta(days=plan.duration_days)
        membership = Membership.objects.create(
            tenant=tenant,
            customer=customer,
            plan=plan,
            start_date=start,
            end_date=end,
            status="active" if end >= dt.date.today() else "expired",
            auto_renew=random.random() > 0.5,
        )
        # ~1 in 10 payments stay pending → feeds the pending-payments widget.
        is_pending = random.random() < 0.1
        payment = Payment.objects.create(
            tenant=tenant,
            customer=customer,
            membership=membership,
            amount=plan.price,
            payment_method=random.choice(["upi", "card", "cash", "online"]),
            status="pending" if is_pending else "completed",
            transaction_id=f"TXN{customer.id:06d}{random.randint(100, 999)}",
            razorpay_order_id=f"order_{customer.id}{random.randint(1000, 9999)}",
            razorpay_payment_id=f"pay_{customer.id}{random.randint(1000, 9999)}",
            paid_at=None if is_pending else timezone.now() - dt.timedelta(days=random.randint(0, 30)),
            notes="",
        )
        if is_pending:
            continue
        Invoice.objects.create(
            tenant=tenant,
            customer=customer,
            payment=payment,
            subtotal=plan.price,
            tax=(plan.price * Decimal("0.18")).quantize(Decimal("0.01")),
            total=(plan.price * Decimal("1.18")).quantize(Decimal("0.01")),
            generated_at=payment.paid_at,
        )


def _seed_diet(tenant, echo) -> None:
    """Seed the 3 template diet plans (skips silently without a FoodItem catalog)."""
    if DietPlan.objects.filter(tenant=tenant, name="Weight Loss Plan").exists():
        return
    if not FoodItem.objects.exists():
        echo("  diet skipped: no FoodItem catalog (run with catalogs)")
        return
    plans_data = [
        ("Weight Loss Plan", "cut", 1500, 0.35, 0.4, 0.25, 30),
        ("Muscle Gain Plan", "bulk", 2800, 0.30, 0.45, 0.25, 30),
        ("Maintenance Plan", "maintain", 2000, 0.25, 0.45, 0.30, 21),
    ]
    for name, goal, cal, pr, cr, fr, dur in plans_data:
        plan = DietPlan.objects.create(
            tenant=tenant,
            name=name,
            description=f"{name} tailored for Indian diet.",
            goal=goal,
            daily_calories=cal,
            protein_ratio=pr,
            carb_ratio=cr,
            fat_ratio=fr,
            duration_days=dur,
            is_template=True,
        )
        for d in range(1, 8):
            day = DietDay.objects.create(tenant=tenant, diet_plan=plan, day_number=d, total_calories=cal)
            for meal_type, group, _frac in [
                ("breakfast", "grains", 0.30),
                ("morning_snack", "fruit", 0.10),
                ("lunch", "protein", 0.30),
                ("evening_snack", "snack", 0.10),
                ("dinner", "protein", 0.20),
            ]:
                items = list(FoodItem.objects.filter(food_group=group))
                if not items:
                    continue
                fi = random.choice(items)
                qty = round(random.uniform(0.8, 1.5), 1)
                DietMeal.objects.create(
                    tenant=tenant,
                    diet_day=day,
                    meal_type=meal_type,
                    food_item=fi,
                    quantity=qty,
                    calories=round(fi.calories * qty, 0),
                    protein=round(fi.protein * qty, 1),
                    carbs=round(fi.carbs * qty, 1),
                    fat=round(fi.fat * qty, 1),
                )


def _seed_workouts(tenant, customers, echo) -> None:
    if WorkoutPlan.objects.filter(tenant=tenant, name="Upper Lower Split").exists():
        return
    strength = list(Exercise.objects.filter(tenant=tenant, category__name="Strength"))
    cardio = list(Exercise.objects.filter(tenant=tenant, category__name="Cardio"))
    if not strength or not cardio:
        echo("  workouts skipped: no Strength/Cardio exercises for tenant (run with catalogs)")
        return
    plans_data = [
        ("Upper Lower Split", "hypertrophy", "intermediate", 4),
        ("Fat Burn Circuit", "weight_loss", "beginner", 4),
        ("Strength Foundation", "strength", "beginner", 4),
    ]
    focus_cycle = ["Chest & Back", "Legs & Core", "Shoulders & Arms", "Full Body"]
    for name, goal, diff, weeks in plans_data:
        plan = WorkoutPlan.objects.create(
            tenant=tenant,
            name=name,
            description=f"{name} program.",
            goal=goal,
            difficulty=diff,
            duration_weeks=weeks,
            is_template=True,
        )
        for i, day in enumerate(["monday", "tuesday", "thursday", "friday"]):
            wd = WorkoutDay.objects.create(
                tenant=tenant,
                workout_plan=plan,
                day_of_week=day,
                day_number=i + 1,
                focus=focus_cycle[i % 4],
                notes="",
            )
            for order in range(1, 6):
                pool = strength if order <= 4 else cardio
                ex = random.choice(pool)
                WorkoutExercise.objects.create(
                    tenant=tenant,
                    workout_day=wd,
                    exercise=ex,
                    sets=random.choice([3, 4, 5]),
                    reps=random.choice(["8-12", "6-8", "15-20"]),
                    rest_seconds=random.choice([60, 90, 120]),
                    tempo=random.choice(["2-1-2", "3-0-1", "2-0-0"]),
                    rpe=random.randint(6, 9),
                    notes="",
                    order=order,
                )
    for customer in random.sample(customers, min(10, len(customers))):
        if WorkoutAssignment.objects.filter(customer=customer).exists():
            continue
        plan = random.choice(list(WorkoutPlan.objects.filter(tenant=tenant)))
        WorkoutAssignment.objects.create(
            tenant=tenant,
            customer=customer,
            workout_plan=plan,
            start_date=dt.date.today() - dt.timedelta(days=15),
            end_date=dt.date.today() + dt.timedelta(days=45),
            is_active=True,
            notes="",
        )


def _seed_operations(tenant, branch, customers, trainers) -> None:
    for i, customer in enumerate(customers):
        trainer = trainers[i % len(trainers)]
        if not TrainerAssignment.objects.filter(customer=customer).exists():
            TrainerAssignment.objects.create(
                tenant=tenant,
                trainer=trainer,
                customer=customer,
                branch=branch,
                assigned_at=timezone.now() - dt.timedelta(days=random.randint(10, 60)),
                is_active=True,
            )
    for trainer in trainers:
        for m in range(3):
            month = (dt.date.today().replace(day=1) - dt.timedelta(days=m * 31)).replace(day=1)
            if not TrainerPerformance.objects.filter(trainer=trainer, month=month).exists():
                TrainerPerformance.objects.create(
                    tenant=tenant,
                    trainer=trainer,
                    month=month,
                    revenue=random.randint(30000, 120000),
                    customer_count=random.randint(8, 15),
                    rating_avg=round(random.uniform(4.2, 4.9), 1),
                    sessions_completed=random.randint(40, 120),
                )
    for customer in random.sample(customers, min(14, len(customers))):
        for d in range(0, 14, 2):
            date = dt.date.today() - dt.timedelta(days=d)
            if AttendanceRecord.objects.filter(customer=customer, date=date).exists():
                continue
            check_in = timezone.make_aware(
                dt.datetime.combine(date, dt.time(random.randint(6, 9), random.choice([0, 30])))
            )
            AttendanceRecord.objects.create(
                tenant=tenant,
                customer=customer,
                branch=branch,
                check_in_time=check_in,
                check_out_time=check_in + dt.timedelta(minutes=random.randint(45, 120)),
                method=random.choice(["qr", "mobile", "manual"]),
                date=date,
            )
    for customer in random.sample(customers, min(10, len(customers))):
        if Feedback.objects.filter(customer=customer).exists():
            continue
        Feedback.objects.create(
            tenant=tenant,
            customer=customer,
            rating=random.randint(3, 5),
            category=random.choice(["workout", "trainer", "facility", "app"]),
            comment=random.choice(
                [
                    "Great trainers and clean facility!",
                    "Equipment could use more maintenance.",
                    "Love the group classes, very motivating.",
                    "The app is easy to use for tracking.",
                ]
            ),
            is_anonymous=False,
        )


def _seed_marketplace_carts(tenant, customers) -> None:
    products = list(Product.objects.filter(tenant=tenant))
    for customer in random.sample(customers, min(6, len(customers))):
        if Cart.objects.filter(user=customer.user, status="active").exists():
            continue
        cart = Cart.objects.create(tenant=tenant, user=customer.user, status="active")
        for product in random.sample(products, random.randint(1, 3)):
            CartItem.objects.create(
                tenant=tenant,
                cart=cart,
                product=product,
                quantity=random.randint(1, 2),
                unit_price=product.price,
            )


@transaction.atomic
def seed_realistic(tenant, branch, trainers, echo=print) -> None:
    """Full realistic tenant-1 dataset (``--realistic``)."""
    random.seed(42)
    created = _seed_customers(tenant, branch)
    customers = list(Customer.objects.filter(tenant=tenant))
    _seed_plans(tenant, customers)
    ensure_demo_payments(tenant, customers)
    _seed_diet(tenant, echo)
    _seed_workouts(tenant, customers, echo)
    _seed_operations(tenant, branch, customers, trainers)
    _seed_marketplace_carts(tenant, customers)
    echo(
        f"  tenant-1 realistic: {len(created)} new customers, "
        f"{len(customers)} total, memberships/diet/workouts/ops seeded"
    )
