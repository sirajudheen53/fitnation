"""IronHouse Fitness (tenant 2) — port of QA ``seed_tenant2.py``.

Multi-tenant isolation testing: enterprise tenant in Hyderabad with 2 branches,
own tenant-scoped exercise/product catalogs, staff, and (with ``--realistic``)
customers, memberships, diet/workout plans and operations.

``seed_base`` runs on every ``seed_qa`` invocation (QA needs owner.iron login);
``seed_realistic`` runs with ``--realistic``.
"""

from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.branches.models import Branch, BranchAmenity
from apps.customers.models import BodyMeasurement, Customer, FitnessGoal, HealthProfile
from apps.diet.models import DietAssignment, DietDay, DietMeal, DietPlan, FoodItem
from apps.exercises.models import Exercise, ExerciseCategory
from apps.feedback.models import Feedback
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.marketplace.models import Cart, CartItem, Inventory, Product, ProductCategory
from apps.payments.models import Invoice, Payment
from apps.tenants.models import Tenant, TenantSettings
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.workouts.models import WorkoutAssignment, WorkoutDay, WorkoutExercise, WorkoutPlan

from .common import (
    PASSWORDS,
    ensure_demo_payments,
    ensure_trainer,
    ensure_trainer_schedule,
    ensure_user,
)

PASSWORD = PASSWORDS["tenant2_staff"]

EXERCISES = [
    ("Overhead Press", "Strength"), ("Power Clean", "Strength"),
    ("Cable Fly", "Strength"), ("Hammer Curl", "Strength"),
    ("Box Jump", "Cardio"), ("Sled Push", "Cardio"),
    ("Battle Ropes", "Cardio"), ("Rowing Machine", "Cardio"),
    ("PVC Mobility Flow", "Mobility"), ("Hip Hinge Warmup", "Mobility"),
    ("Lat Stretch", "Flexibility"), ("Kneeling Quad Stretch", "Flexibility"),
]

CUSTOMERS = [
    ("Imran", "Shaikh", "imran.s@gmail.com", "male", 176, 84),
    ("Zoya", "Ahmed", "zoya.ahmed@gmail.com", "female", 160, 56),
    ("Harsha", "Vardhan", "harsha.v@gmail.com", "male", 180, 92),
    ("Nidhi", "Bisht", "nidhi.bisht@gmail.com", "female", 165, 64),
    ("Pranav", "Kothari", "pranav.k@gmail.com", "male", 177, 80),
    ("Simran", "Kaur", "simran.kaur@gmail.com", "female", 162, 55),
    ("Tej", "Reddy", "tej.reddy@gmail.com", "male", 179, 78),
    ("Anushka", "Purohit", "anushka.p@gmail.com", "female", 158, 68),
    ("Harshal", "Desai", "harshal.d@gmail.com", "male", 172, 90),
    ("Meghna", "Nayak", "meghna.nayak@gmail.com", "female", 167, 61),
    ("Ritesh", "Sodhi", "ritesh.sodhi@gmail.com", "male", 175, 88),
    ("Kirti", "Bansal", "kirti.bansal@gmail.com", "female", 160, 56),
    ("Naveen", "Prasad", "naveen.p@gmail.com", "male", 181, 79),
    ("Charu", "Malik", "charu.malik@gmail.com", "female", 163, 72),
]

TENANT_EMAIL = "ironhouse@fitnation.test"


def _seed_tenant() -> Tenant:
    tenant = Tenant.objects.filter(contact_email=TENANT_EMAIL).first()
    if tenant is None:
        tenant = Tenant.objects.create(
            name="IronHouse Fitness",
            legal_name="IronHouse Fitness Pvt Ltd",
            subscription_plan="enterprise",
            status="active",
            contact_email=TENANT_EMAIL,
            contact_phone="+914012345678",
            timezone="Asia/Kolkata",
            settings={"brand": "IronHouse", "theme": "dark"},
        )
    TenantSettings.objects.get_or_create(
        tenant=tenant,
        defaults=dict(max_branches=3, max_customers=500, max_trainers=20,
                      primary_color="#DC2626", enable_whatsapp=True,
                      enable_razorpay=True),
    )
    return tenant


def _seed_branches(tenant: Tenant) -> list[Branch]:
    branches = []
    specs = [
        ("Secunderabad", "flagship", "42, Rasoolpura Main Road", "Secunderabad",
         "500003", 17.4375, 78.4986, "+914012345678", "secunderabad@ironhouse.test",
         "05:00", "23:00", True),
        ("Gachibowli", "standard", "78, Financial District", "Gachibowli",
         "500032", 17.4401, 78.3489, "+914045678901", "gachibowli@ironhouse.test",
         "05:30", "22:30", False),
    ]
    for (name, btype, line1, line2, postal, lat, lng, phone, email,
         opens, closes, hq) in specs:
        branch = Branch.objects.filter(tenant=tenant, name=name).first()
        if branch is None:
            branch = Branch.objects.create(
                tenant=tenant, name=name, branch_type=btype,
                address_line1=line1, address_line2=line2,
                city="Hyderabad", state="Telangana", postal_code=postal,
                country="IN", latitude=lat, longitude=lng,
                phone=phone, email=email,
                opening_time=opens, closing_time=closes,
                operating_days=["monday", "tuesday", "wednesday", "thursday",
                                "friday", "saturday", "sunday"] if hq else
                ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
                is_active=True, is_headquarters=hq,
            )
        branches.append(branch)
    for branch in branches:
        for amenity in ["Steam Room", "CrossFit Rig", "Parking", "Whey Bar", "Showers"]:
            BranchAmenity.objects.get_or_create(
                branch=branch, name=amenity, defaults={"is_available": True})
    return branches


def _seed_exercises(tenant: Tenant) -> None:
    categories = {}
    for cname in ["Strength", "Cardio", "Flexibility", "Mobility"]:
        cat, _ = ExerciseCategory.objects.get_or_create(
            tenant=tenant, name=cname,
            defaults=dict(description=f"{cname} exercises", slug=cname.lower()),
        )
        categories[cname] = cat
    for name, cname in EXERCISES:
        Exercise.objects.get_or_create(
            tenant=tenant, name=name,
            defaults=dict(
                description=f"{name} for {cname.lower()} training.",
                category=categories[cname],
                muscle_groups=["full_body"],
                equipment_needed=["none"],
                difficulty=random.choice(["beginner", "intermediate"]),
                instructions=["Setup", "Perform", "Recover"],
                tips="Maintain form.", contraindications="",
            ),
        )


def _seed_products(tenant: Tenant) -> list[Product]:
    pcat, _ = ProductCategory.objects.get_or_create(
        tenant=tenant, slug="supplements",
        defaults=dict(name="Supplements", description="Sports nutrition"),
    )
    gcat, _ = ProductCategory.objects.get_or_create(
        tenant=tenant, slug="apparel",
        defaults=dict(name="Apparel", description="Training gear"),
    )
    items = [
        ("IronHouse Whey Protein 1kg", pcat, "IH-WHEY-1", 2450, 3000, 15),
        ("BCAA 2:1:1 (500g)", pcat, "IH-BCAA-5", 1200, 1500, 8),
        ("Creatine Monohydrate 300g", pcat, "IH-CRTR-3", 900, 1100, 6),
        ("Dry-Fit Training Tee", gcat, "IH-TEE-M", 799, 999, 25),
        ("CrossFit Shorts", gcat, "IH-SHRT-L", 1099, 1299, 12),
    ]
    for name, cat, sku, price, compare, stock in items:
        product, _ = Product.objects.get_or_create(
            tenant=tenant, sku=sku,
            defaults=dict(category=cat, name=name,
                          slug=sku.lower().replace(" ", "-"),
                          description=name, price=price, compare_price=compare,
                          barcode=sku, brand="IronHouse", status="active"),
        )
        Inventory.objects.get_or_create(
            tenant=tenant, product=product,
            defaults=dict(stock_quantity=stock, low_stock_threshold=5,
                          track_inventory=True),
        )
    return list(Product.objects.filter(tenant=tenant))


def _seed_staff(tenant: Tenant, reset_passwords: bool) -> list:
    specs = [
        ("trainer.iron1@fitnation.test", "Danish", "Qureshi", "Powerlifting", 8),
        ("trainer.iron2@fitnation.test", "Preeti", "Verma", "CrossFit", 5),
    ]
    staff_specs = [
        ("owner.iron@fitnation.test", "Rohan", "Kapoor", "gym_owner"),
        ("manager.iron@fitnation.test", "Sanya", "Gill", "manager"),
        ("diet.iron@fitnation.test", "Farah", "Khan", "dietitian"),
    ]
    for email, fn, ln, role in staff_specs:
        ensure_user(
            email=email, first_name=fn, last_name=ln, role=role,
            password=PASSWORD, tenant=tenant,
            phone=f"+91{random.randint(7000000000, 9999999999)}",
            reset_passwords=reset_passwords,
        )
    trainers = []
    for email, fn, ln, spec, yrs in specs:
        user = ensure_user(
            email=email, first_name=fn, last_name=ln, role="trainer",
            password=PASSWORD, tenant=tenant,
            phone=f"+91{random.randint(7000000000, 9999999999)}",
            is_staff=False, reset_passwords=reset_passwords,
        )
        trainer = ensure_trainer(
            user, specialization=spec, bio=f"{fn} coaches {spec} at IronHouse.",
            is_active=True, certifications=["CrossFit L1", "ACE"],
            experience_years=yrs, rating=4.8, max_clients=12,
        )
        ensure_trainer_schedule(
            trainer, tenant,
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
            "06:00", "20:00",
        )
        trainers.append(trainer)
    return trainers


def seed_base(reset_passwords: bool = True, echo=print) -> tuple:
    """Tenant + branches + catalogs + staff. Runs on default ``seed_qa``."""
    random.seed(2026)
    tenant = _seed_tenant()
    branches = _seed_branches(tenant)
    _seed_exercises(tenant)
    products = _seed_products(tenant)
    trainers = _seed_staff(tenant, reset_passwords)
    echo(f"  IronHouse: tenant + {len(branches)} branches + catalogs + "
         f"{len(trainers)} trainers + staff")
    return tenant, branches, trainers, products


def _seed_customers(tenant: Tenant, branches: list[Branch]) -> list[Customer]:
    created = []
    for name, lname, email, gender, hgt, wgt in CUSTOMERS:
        if Customer.objects.filter(email=email).exists():
            continue
        branch = random.choice(branches)
        user = ensure_user(
            email=email, first_name=name, last_name=lname, role="customer",
            password=PASSWORDS["tenant2_customers"], tenant=tenant,
            phone=f"+91{random.randint(7000000000, 9999999999)}", is_staff=False,
        )
        customer = Customer.objects.create(
            tenant=tenant, user=user, branch=branch, name=f"{name} {lname}",
            email=email, phone=user.phone, gender=gender,
            date_of_birth=dt.date(1990 - random.randint(0, 18), random.randint(1, 12), random.randint(1, 28)),
            emergency_contact_name=f"Relative of {name}",
            emergency_contact_phone="+918000000000",
            address_street=f"{random.randint(1, 300)}, {random.choice(['Banjara Hills', 'Madhapur', 'Kondapur', 'Gachibowli'])}",
            address_city="Hyderabad", address_state="Telangana",
            address_postal_code=str(random.randint(500001, 500100)),
            status=random.choice(["active", "active", "active", "inactive"]),
            is_active=True,
        )
        HealthProfile.objects.create(
            tenant=tenant, customer=customer, height_cm=hgt, weight_kg=wgt,
            bmi=round(wgt / (hgt / 100) ** 2, 1),
            blood_group=random.choice(["A+", "B+", "O+", "AB+", "O-"]),
            injuries="", current_injuries=[], past_injuries=[], medical_info={},
            medical_conditions=[], allergies=[], food_allergies=[],
            medications=[], dietary_restrictions=[],
        )
        FitnessGoal.objects.create(
            tenant=tenant, customer=customer,
            goal_type=random.choice(["lose_weight", "build_muscle", "endurance", "general_fitness"]),
            is_active=True, status="active", target_value=random.choice([5, 10, 15]),
            target_unit=random.choice(["kg", "%", "min", ""]),
            target_date=dt.date.today() + dt.timedelta(days=random.randint(60, 180)),
            current_value=0, notes="",
        )
        BodyMeasurement.objects.create(
            tenant=tenant, customer=customer, date_logged=dt.date.today(),
            weight_kg=wgt, height_cm=hgt, bmi=round(wgt / (hgt / 100) ** 2, 1),
            body_fat_percentage=round(random.uniform(15, 32), 1),
            chest_cm=round(random.uniform(88, 112), 1), waist_cm=round(random.uniform(70, 102), 1),
            hips_cm=round(random.uniform(88, 106), 1), biceps_cm=round(random.uniform(28, 39), 1),
            thighs_cm=round(random.uniform(50, 66), 1), neck_cm=round(random.uniform(34, 42), 1),
            notes="",
        )
        created.append(customer)
    return created


def _seed_memberships(tenant: Tenant, customers: list[Customer]) -> None:
    plans = []
    pdata = [
        ("IronHourly Pass", "trial", 1000, 1, "Day pass + 1 session"),
        ("Iron Monthly", "monthly", 2000, 30, "Full gym access"),
        ("Iron Pro Yearly", "yearly", 18000, 365, "All branches + PT credit"),
        ("Iron Power PT", "pt", 7500, 30, "Monthly + 10 PT sessions"),
    ]
    for name, ptype, price, dur, desc in pdata:
        plan, _ = MembershipPlan.objects.get_or_create(
            tenant=tenant, name=name,
            defaults=dict(plan_type=ptype, price=price, duration_days=dur,
                          description=desc, is_active=True),
        )
        plans.append(plan)
    Coupon.objects.get_or_create(
        tenant=tenant, code="IRON20",
        defaults=dict(discount_percent=20, max_uses=50, used_count=3,
                      valid_from=dt.date.today() - dt.timedelta(days=15),
                      valid_to=dt.date.today() + dt.timedelta(days=45), is_active=True))
    for customer in customers:
        if Membership.objects.filter(customer=customer).exists():
            continue
        plan = random.choice(plans)
        start = dt.date.today() - dt.timedelta(days=random.randint(3, 180))
        end = start + dt.timedelta(days=plan.duration_days)
        membership = Membership.objects.create(
            tenant=tenant, customer=customer, plan=plan,
            start_date=start, end_date=end,
            status="active" if end >= dt.date.today() else "expired",
            auto_renew=random.random() > 0.5)
        is_pending = random.random() < 0.1
        payment = Payment.objects.create(
            tenant=tenant, customer=customer, membership=membership, amount=plan.price,
            payment_method=random.choice(["upi", "card", "cash", "online"]),
            status="pending" if is_pending else "completed",
            transaction_id=f"IH-TXN{customer.id:05d}{random.randint(100, 999)}",
            razorpay_order_id=f"order_ih{customer.id}{random.randint(1000, 9999)}",
            razorpay_payment_id=f"pay_ih{customer.id}{random.randint(1000, 9999)}",
            paid_at=None if is_pending else timezone.now() - dt.timedelta(days=random.randint(0, 30)),
            notes="")
        if is_pending:
            continue
        Invoice.objects.create(
                tenant=tenant, customer=customer, payment=payment,
                subtotal=plan.price,
                tax=(plan.price * Decimal("0.18")).quantize(Decimal("0.01")),
                total=(plan.price * Decimal("1.18")).quantize(Decimal("0.01")),
                generated_at=payment.paid_at)


def _seed_diet(tenant: Tenant, customers: list[Customer], echo) -> None:
    if DietPlan.objects.filter(tenant=tenant, name="Iron Cut Diet").exists():
        return
    if not FoodItem.objects.exists():
        echo("  IronHouse diet skipped: no FoodItem catalog (run with catalogs)")
        return
    plans = [
        ("Iron Cut Diet", "cut", 1600, 0.35, 0.40, 0.25, 30),
        ("Iron Bulk Diet", "bulk", 2900, 0.30, 0.45, 0.25, 30),
    ]
    for name, goal, cal, pr, cr, fr, dur in plans:
        plan = DietPlan.objects.create(
            tenant=tenant, name=name, description=f"{name} for IronHouse members.",
            goal=goal, daily_calories=cal, protein_ratio=pr, carb_ratio=cr,
            fat_ratio=fr, duration_days=dur, is_template=True)
        for d in range(1, 8):
            day = DietDay.objects.create(tenant=tenant, diet_plan=plan, day_number=d, total_calories=cal)
            for meal_type, group, _frac in [
                ("breakfast", "grains", 0.3), ("morning_snack", "fruit", 0.1),
                ("lunch", "protein", 0.3), ("evening_snack", "snack", 0.1),
                ("dinner", "protein", 0.2),
            ]:
                items = list(FoodItem.objects.filter(food_group=group))
                if not items:
                    continue
                fi = random.choice(items)
                qty = round(random.uniform(0.8, 1.5), 1)
                DietMeal.objects.create(
                    tenant=tenant, diet_day=day, meal_type=meal_type, food_item=fi,
                    quantity=qty, calories=round(fi.calories * qty, 0),
                    protein=round(fi.protein * qty, 1), carbs=round(fi.carbs * qty, 1),
                    fat=round(fi.fat * qty, 1))
    for customer in random.sample(customers, min(6, len(customers))):
        plan = random.choice(list(DietPlan.objects.filter(tenant=tenant)))
        if not DietAssignment.objects.filter(customer=customer).exists():
            DietAssignment.objects.create(
                tenant=tenant, customer=customer, diet_plan=plan,
                start_date=dt.date.today() - dt.timedelta(days=10),
                is_active=True, notes="")


def _seed_workouts(tenant: Tenant, customers: list[Customer], echo) -> None:
    if WorkoutPlan.objects.filter(tenant=tenant, name="Iron Push + Pull + Legs").exists():
        return
    strength = list(Exercise.objects.filter(tenant=tenant, category__name="Strength"))
    cardio = list(Exercise.objects.filter(tenant=tenant, category__name="Cardio"))
    if not strength or not cardio:
        echo("  IronHouse workouts skipped: no Strength/Cardio exercises")
        return
    plans = [
        ("Iron Push + Pull + Legs", "hypertrophy", "intermediate", 4),
        ("Iron Strength Basics", "strength", "beginner", 4),
    ]
    focus_cycle = ["Push", "Pull", "Legs", "Core"]
    for name, goal, diff, weeks in plans:
        plan = WorkoutPlan.objects.create(
            tenant=tenant, name=name, description=f"{name} at IronHouse.",
            goal=goal, difficulty=diff, duration_weeks=weeks, is_template=True)
        for i, day in enumerate(["monday", "wednesday", "friday"]):
            wd = WorkoutDay.objects.create(
                tenant=tenant, workout_plan=plan, day_of_week=day,
                day_number=i + 1, focus=focus_cycle[i % 4], notes="")
            for order in range(1, 6):
                pool = strength if order <= 4 else cardio
                ex = random.choice(pool)
                WorkoutExercise.objects.create(
                    tenant=tenant, workout_day=wd, exercise=ex,
                    sets=random.choice([3, 4, 5]), reps=random.choice(["8-12", "6-8", "12-15"]),
                    rest_seconds=random.choice([60, 90, 120]),
                    tempo=random.choice(["2-1-2", "3-0-1"]),
                    rpe=random.randint(6, 9), order=order)
    for customer in random.sample(customers, min(8, len(customers))):
        plan = random.choice(list(WorkoutPlan.objects.filter(tenant=tenant)))
        if not WorkoutAssignment.objects.filter(customer=customer).exists():
            WorkoutAssignment.objects.create(
                tenant=tenant, customer=customer, workout_plan=plan,
                start_date=dt.date.today() - dt.timedelta(days=12),
                end_date=dt.date.today() + dt.timedelta(days=45), is_active=True)


def _seed_operations(tenant: Tenant, customers: list[Customer], trainers: list) -> None:
    for i, customer in enumerate(customers):
        trainer = trainers[i % len(trainers)]
        if not TrainerAssignment.objects.filter(customer=customer).exists():
            TrainerAssignment.objects.create(
                tenant=tenant, trainer=trainer, customer=customer,
                branch=customer.branch,
                assigned_at=timezone.now() - dt.timedelta(days=random.randint(10, 60)),
                is_active=True)
    for trainer in trainers:
        for m in range(3):
            month = (dt.date.today().replace(day=1) - dt.timedelta(days=m * 31)).replace(day=1)
            if not TrainerPerformance.objects.filter(trainer=trainer, month=month).exists():
                TrainerPerformance.objects.create(
                    tenant=tenant, trainer=trainer, month=month,
                    revenue=random.randint(25000, 90000),
                    customer_count=random.randint(6, 14),
                    rating_avg=round(random.uniform(4.1, 4.8), 1),
                    sessions_completed=random.randint(30, 100))
    for customer in random.sample(customers, min(10, len(customers))):
        for d in range(0, 14, 2):
            date = dt.date.today() - dt.timedelta(days=d)
            if AttendanceRecord.objects.filter(customer=customer, date=date).exists():
                continue
            check_in = timezone.make_aware(
                dt.datetime.combine(date, dt.time(random.randint(6, 9), random.choice([0, 30]))))
            AttendanceRecord.objects.create(
                tenant=tenant, customer=customer, branch=customer.branch,
                check_in_time=check_in,
                check_out_time=check_in + dt.timedelta(minutes=random.randint(45, 120)),
                method=random.choice(["qr", "mobile", "manual"]), date=date)
    for customer in random.sample(customers, min(8, len(customers))):
        if not Feedback.objects.filter(customer=customer).exists():
            Feedback.objects.create(
                tenant=tenant, customer=customer, rating=random.randint(3, 5),
                category=random.choice(["workout", "trainer", "facility", "app"]),
                comment=random.choice(["Solid equipment and coaching.",
                                       "PT sessions are worth it.",
                                       "Branch is clean and well-maintained.",
                                       "Booking via app is easy."]),
                is_anonymous=False)


def _seed_marketplace(tenant: Tenant, customers: list[Customer], products: list[Product]) -> None:
    for customer in random.sample(customers, min(4, len(customers))):
        if Cart.objects.filter(user=customer.user, status="active").exists():
            continue
        cart = Cart.objects.create(tenant=tenant, user=customer.user, status="active")
        for product in random.sample(products, random.randint(1, 2)):
            CartItem.objects.create(
                tenant=tenant, cart=cart, product=product,
                quantity=random.randint(1, 2), unit_price=product.price)


@transaction.atomic
def seed_realistic(reset_passwords: bool = True, echo=print) -> None:
    """Full IronHouse dataset (``--realistic``)."""
    random.seed(2026)
    tenant, branches, trainers, products = seed_base(reset_passwords=reset_passwords, echo=lambda *_: None)
    customers = _seed_customers(tenant, branches)
    _seed_memberships(tenant, customers)
    ensure_demo_payments(tenant, customers)
    _seed_diet(tenant, customers, echo)
    _seed_workouts(tenant, customers, echo)
    _seed_operations(tenant, customers, trainers)
    _seed_marketplace(tenant, customers, products)
    echo(f"  IronHouse realistic: {len(customers)} customers, "
         "memberships/diet/workouts/ops seeded")