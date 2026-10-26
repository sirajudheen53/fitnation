"""Seed the global catalogue with common dishes/meals (ticket #89).

Usage::

    python manage.py seed_dishes [--reset]

Populates 120+ common dishes (Indian-heavy plus standard/Western) with
realistic per-serving macros and a natural meal-type tag. Dishes are global
catalogue rows (``tenant`` NULL), so the command runs once per platform and
every tenant sees the catalogue. Re-runs are idempotent (``get_or_create``).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.diet.models import FoodItem

# name, serving_size, calories, protein, carbs, fat, fiber, meal_type, is_veg, food_group
_DISH_DATA: list[tuple] = [
    # ── Breakfast — South Indian ────────────────────────────────────────────────
    ("Idli Sambar", "2 pieces", 250, 8.0, 45.0, 3.5, 4.0, "breakfast", True, "grains"),
    ("Masala Dosa", "1 piece", 290, 6.0, 38.0, 13.0, 3.0, "breakfast", True, "grains"),
    ("Mysore Masala Dosa", "1 piece", 330, 6.5, 44.0, 15.0, 3.0, "breakfast", True, "grains"),
    ("Rava Dosa", "2 pieces", 240, 5.0, 38.0, 8.0, 2.0, "breakfast", True, "grains"),
    ("Set Dosa", "2 pieces", 260, 7.0, 42.0, 7.0, 2.5, "breakfast", True, "grains"),
    ("Neer Dosa", "2 pieces", 180, 4.0, 36.0, 2.0, 1.5, "breakfast", True, "grains"),
    ("Medu Vada", "2 pieces", 280, 7.0, 30.0, 15.0, 3.0, "breakfast", True, "grains"),
    ("Onion Tomato Uttapam", "1 piece", 230, 5.0, 38.0, 7.0, 3.0, "breakfast", True, "grains"),
    ("Rava Idli", "2 pieces", 200, 5.0, 34.0, 5.0, 2.0, "breakfast", True, "grains"),
    ("Oats Idli", "2 pieces", 180, 6.0, 30.0, 4.0, 3.0, "breakfast", True, "grains"),
    ("Appam", "2 pieces", 240, 4.0, 44.0, 4.0, 2.0, "breakfast", True, "grains"),
    ("Idiyappam", "2 pieces", 220, 4.0, 46.0, 2.0, 2.5, "breakfast", True, "grains"),
    ("Puttu with Kadala Curry", "1 serving", 420, 12.0, 60.0, 13.0, 6.0, "breakfast", True, "protein"),
    ("Pongal", "1 bowl (200g)", 320, 8.0, 48.0, 10.0, 3.0, "breakfast", True, "grains"),
    # ── Breakfast — North Indian & general ──────────────────────────────────────
    ("Vegetable Upma", "1 bowl (200g)", 300, 7.0, 48.0, 8.0, 5.0, "breakfast", True, "grains"),
    ("Kanda Poha", "1 bowl (200g)", 250, 5.0, 48.0, 5.0, 3.0, "breakfast", True, "grains"),
    ("Aloo Paratha", "1 piece", 320, 7.0, 44.0, 13.0, 4.0, "breakfast", True, "grains"),
    ("Paneer Paratha", "1 piece", 350, 12.0, 40.0, 16.0, 3.5, "breakfast", True, "protein"),
    ("Methi Thepla", "2 pieces", 240, 6.0, 34.0, 8.0, 3.5, "breakfast", True, "grains"),
    ("Besan Chilla", "2 pieces", 220, 10.0, 26.0, 8.0, 4.0, "breakfast", True, "protein"),
    ("Moong Dal Chilla", "2 pieces", 240, 12.0, 28.0, 8.0, 4.5, "breakfast", True, "protein"),
    ("Sabudana Khichdi", "1 bowl", 290, 5.0, 52.0, 8.0, 2.5, "breakfast", True, "grains"),
    ("Misal Pav", "1 plate", 400, 12.0, 52.0, 15.0, 6.0, "breakfast", True, "protein"),
    ("Puri Bhaji", "1 plate", 450, 8.0, 60.0, 20.0, 5.0, "breakfast", True, "grains"),
    ("Oats Porridge (with milk)", "1 bowl", 220, 8.0, 34.0, 5.0, 4.0, "breakfast", True, "dairy"),
    ("Overnight Oats with Fruits", "1 jar", 320, 13.0, 44.0, 9.0, 6.0, "breakfast", True, "dairy"),
    ("Cornflakes with Milk", "1 bowl", 210, 8.0, 38.0, 3.0, 1.0, "breakfast", True, "dairy"),
    ("Pancakes with Syrup", "2 pieces", 350, 8.0, 55.0, 11.0, 1.5, "breakfast", True, "grains"),
    ("French Toast", "2 slices", 300, 11.0, 32.0, 14.0, 2.0, "breakfast", False, "protein"),
    ("Bread Omelette", "1 serving", 280, 13.0, 22.0, 16.0, 1.5, "breakfast", False, "protein"),
    ("Masala Omelette", "2 eggs", 200, 13.0, 3.0, 16.0, 0.5, "breakfast", False, "protein"),
    ("Egg Bhurji", "1 bowl (2 eggs)", 240, 13.0, 6.0, 19.0, 0.5, "breakfast", False, "protein"),
    ("Egg Curry", "1 bowl (2 eggs)", 290, 14.0, 10.0, 21.0, 1.5, "breakfast", False, "protein"),
    ("Paneer Bhurji", "1 bowl (150g)", 300, 16.0, 8.0, 24.0, 1.5, "breakfast", True, "protein"),
    ("Croissant", "1 piece", 230, 5.0, 26.0, 12.0, 1.5, "breakfast", True, "grains"),
    ("Bagel with Cream Cheese", "1 serving", 320, 10.0, 48.0, 10.0, 2.0, "breakfast", True, "dairy"),
    # ── Veg curries & mains ─────────────────────────────────────────────────────
    ("Dal Tadka", "1 bowl (150g)", 180, 9.0, 22.0, 6.0, 5.0, "lunch", True, "protein"),
    ("Dal Palak", "1 bowl (150g)", 190, 9.0, 22.0, 7.0, 5.5, "lunch", True, "protein"),
    ("Dal Makhani", "1 bowl (150g)", 330, 9.0, 28.0, 20.0, 5.0, "lunch", True, "protein"),
    ("Rajma Masala", "1 bowl (150g)", 250, 10.0, 35.0, 7.0, 8.0, "lunch", True, "protein"),
    ("Chana Masala", "1 bowl (150g)", 260, 9.0, 34.0, 9.0, 8.0, "lunch", True, "protein"),
    ("Sambar", "1 bowl (150g)", 120, 6.0, 18.0, 3.0, 4.0, "lunch", True, "protein"),
    ("Rasam", "1 bowl (150g)", 60, 3.0, 9.0, 1.5, 1.0, "lunch", True, "protein"),
    ("Kadhi Pakora", "1 bowl (200g)", 250, 9.0, 20.0, 15.0, 2.0, "lunch", True, "dairy"),
    ("Palak Paneer", "1 bowl (150g)", 280, 13.0, 12.0, 20.0, 4.0, "lunch", True, "protein"),
    ("Paneer Butter Masala", "1 bowl (150g)", 350, 14.0, 16.0, 26.0, 2.5, "dinner", True, "protein"),
    ("Kadai Paneer", "1 bowl (150g)", 320, 15.0, 14.0, 24.0, 3.5, "dinner", True, "protein"),
    ("Matar Paneer", "1 bowl (150g)", 300, 13.0, 16.0, 20.0, 4.0, "dinner", True, "protein"),
    ("Malai Kofta", "1 bowl (150g)", 380, 9.0, 24.0, 28.0, 3.0, "dinner", True, "vegetable"),
    ("Vegetable Korma", "1 bowl (150g)", 260, 7.0, 20.0, 18.0, 4.0, "dinner", True, "vegetable"),
    ("Mix Vegetable Curry", "1 bowl (150g)", 200, 6.0, 20.0, 11.0, 5.0, "dinner", True, "vegetable"),
    ("Aloo Gobi", "1 bowl (150g)", 190, 5.0, 25.0, 8.0, 5.0, "lunch", True, "vegetable"),
    ("Bhindi Masala", "1 bowl (150g)", 180, 4.0, 16.0, 12.0, 4.5, "lunch", True, "vegetable"),
    ("Baingan Bharta", "1 bowl (150g)", 170, 4.0, 15.0, 11.0, 4.0, "lunch", True, "vegetable"),
    ("Aloo Matar", "1 bowl (150g)", 210, 6.0, 26.0, 9.0, 4.5, "lunch", True, "vegetable"),
    ("Sarson Ka Saag", "1 bowl (150g)", 190, 6.0, 14.0, 13.0, 6.0, "lunch", True, "vegetable"),
    ("Mushroom Masala", "1 bowl (150g)", 190, 6.0, 14.0, 13.0, 3.0, "dinner", True, "vegetable"),
    ("Paneer Tikka", "1 plate (6 pieces)", 320, 18.0, 10.0, 24.0, 1.0, "snack", True, "protein"),
    # ── Rice, khichdi & noodles ─────────────────────────────────────────────────
    ("Vegetable Biryani", "1 plate (250g)", 450, 10.0, 68.0, 14.0, 5.0, "lunch", True, "grains"),
    ("Veg Pulao", "1 plate (250g)", 380, 8.0, 60.0, 12.0, 4.5, "lunch", True, "grains"),
    ("Jeera Rice", "1 bowl (200g)", 250, 5.0, 44.0, 7.0, 1.5, "lunch", True, "grains"),
    ("Lemon Rice", "1 bowl (200g)", 280, 5.0, 48.0, 9.0, 2.0, "lunch", True, "grains"),
    ("Curd Rice", "1 bowl (200g)", 230, 7.0, 36.0, 6.0, 1.5, "lunch", True, "dairy"),
    ("Bisi Bele Bath", "1 bowl (250g)", 330, 9.0, 52.0, 9.0, 5.0, "lunch", True, "grains"),
    ("Tomato Rice", "1 bowl (200g)", 270, 5.0, 46.0, 8.0, 2.5, "lunch", True, "grains"),
    ("Moong Dal Khichdi", "1 bowl (250g)", 280, 10.0, 48.0, 5.0, 5.0, "dinner", True, "grains"),
    ("Veg Fried Rice", "1 plate (250g)", 420, 9.0, 64.0, 14.0, 3.5, "lunch", True, "grains"),
    ("Hakka Noodles", "1 plate (250g)", 400, 10.0, 58.0, 14.0, 4.0, "lunch", True, "grains"),
    ("White Sauce Pasta", "1 bowl (250g)", 450, 14.0, 52.0, 20.0, 3.0, "dinner", True, "grains"),
    ("Red Sauce Pasta", "1 bowl (250g)", 400, 12.0, 60.0, 12.0, 5.0, "dinner", True, "grains"),
    ("Spaghetti Bolognese", "1 plate", 520, 24.0, 62.0, 18.0, 5.0, "dinner", False, "grains"),
    # ── Non-veg mains ───────────────────────────────────────────────────────────
    ("Butter Chicken", "1 bowl (150g)", 380, 25.0, 10.0, 28.0, 1.0, "dinner", False, "protein"),
    ("Chicken Tikka Masala", "1 bowl (150g)", 320, 28.0, 12.0, 19.0, 1.5, "dinner", False, "protein"),
    ("Chicken Curry (home style)", "1 bowl (150g)", 250, 24.0, 8.0, 15.0, 1.0, "lunch", False, "protein"),
    ("Chicken Biryani", "1 plate (300g)", 550, 25.0, 65.0, 20.0, 2.5, "lunch", False, "protein"),
    ("Mutton Biryani", "1 plate (300g)", 600, 26.0, 68.0, 24.0, 2.5, "lunch", False, "protein"),
    ("Mutton Curry", "1 bowl (150g)", 350, 25.0, 8.0, 26.0, 1.0, "lunch", False, "protein"),
    ("Rogan Josh", "1 bowl (150g)", 340, 25.0, 8.0, 25.0, 0.5, "dinner", False, "protein"),
    ("Chicken Chettinad", "1 bowl (150g)", 300, 25.0, 10.0, 20.0, 1.5, "dinner", False, "protein"),
    ("Chicken Korma", "1 bowl (150g)", 350, 24.0, 14.0, 24.0, 1.5, "dinner", False, "protein"),
    ("Pepper Chicken", "1 bowl (150g)", 280, 26.0, 8.0, 16.0, 0.5, "dinner", False, "protein"),
    ("Tandoori Chicken", "1 piece (quarter)", 220, 27.0, 3.0, 11.0, 0.0, "dinner", False, "protein"),
    ("Fish Curry", "1 bowl (150g)", 250, 22.0, 8.0, 16.0, 0.5, "lunch", False, "protein"),
    ("Fish Fry", "1 piece (100g)", 220, 21.0, 8.0, 13.0, 0.5, "lunch", False, "protein"),
    ("Prawn Masala", "1 bowl (150g)", 220, 22.0, 9.0, 12.0, 0.5, "dinner", False, "protein"),
    ("Chicken Fried Rice", "1 plate (250g)", 480, 18.0, 62.0, 16.0, 2.5, "lunch", False, "grains"),
    ("Egg Fried Rice", "1 plate (250g)", 460, 16.0, 60.0, 16.0, 2.0, "lunch", False, "grains"),
    ("Chicken Manchurian", "1 plate (150g)", 350, 20.0, 24.0, 19.0, 1.5, "snack", False, "protein"),
    ("Chicken 65", "1 plate (150g)", 380, 24.0, 18.0, 24.0, 1.0, "snack", False, "protein"),
    ("Chicken Shawarma Roll", "1 roll", 450, 25.0, 40.0, 20.0, 2.0, "snack", False, "protein"),
    ("Chicken Burger", "1 burger", 450, 22.0, 40.0, 20.0, 2.0, "dinner", False, "protein"),
    ("Grilled Chicken Sandwich", "1 sandwich", 350, 22.0, 35.0, 13.0, 3.0, "lunch", False, "protein"),
    ("Grilled Chicken Salad", "1 bowl (250g)", 280, 28.0, 14.0, 13.0, 3.5, "lunch", False, "protein"),
    ("Chicken Wrap", "1 wrap", 380, 24.0, 38.0, 14.0, 3.0, "lunch", False, "protein"),
    ("Chicken Momos", "1 plate (6 pieces)", 300, 18.0, 40.0, 7.0, 1.5, "snack", False, "protein"),
    ("Keema Pav", "1 plate", 480, 24.0, 38.0, 26.0, 2.0, "snack", False, "protein"),
    ("Chicken Noodle Soup", "1 bowl (250g)", 180, 12.0, 20.0, 5.0, 1.5, "snack", False, "protein"),
    # ── Street food & snacks ────────────────────────────────────────────────────
    ("Vada Pav", "1 piece", 300, 8.0, 42.0, 11.0, 3.0, "snack", True, "grains"),
    ("Pav Bhaji", "1 plate", 500, 12.0, 65.0, 20.0, 6.5, "snack", True, "vegetable"),
    ("Samosa Chaat", "1 plate", 420, 8.0, 52.0, 20.0, 4.5, "snack", True, "snack"),
    ("Papdi Chaat", "1 plate", 250, 5.0, 35.0, 10.0, 3.0, "snack", True, "grains"),
    ("Pani Puri", "1 plate (6 pieces)", 250, 5.0, 42.0, 8.0, 2.0, "snack", True, "grains"),
    ("Dahi Puri", "1 plate (6 pieces)", 280, 6.0, 40.0, 11.0, 2.0, "snack", True, "dairy"),
    ("Dahi Vada", "2 pieces", 280, 9.0, 28.0, 14.0, 2.0, "snack", True, "dairy"),
    ("Aloo Tikki", "2 pieces", 220, 4.0, 28.0, 10.0, 3.0, "snack", True, "vegetable"),
    ("Dhokla", "2 pieces", 160, 6.0, 24.0, 4.0, 2.0, "snack", True, "protein"),
    ("Veg Momos", "1 plate (6 pieces)", 280, 8.0, 48.0, 6.0, 2.5, "snack", True, "vegetable"),
    ("Veg Manchurian", "1 plate (150g)", 320, 7.0, 38.0, 15.0, 3.0, "snack", True, "vegetable"),
    ("Veg Burger", "1 burger", 350, 10.0, 45.0, 14.0, 4.0, "dinner", True, "grains"),
    ("French Fries", "1 medium serving", 330, 4.0, 42.0, 16.0, 3.5, "snack", True, "vegetable"),
    ("Paneer Kathi Roll", "1 roll", 380, 15.0, 42.0, 16.0, 3.5, "snack", True, "protein"),
    ("Margherita Pizza", "2 slices", 400, 16.0, 48.0, 16.0, 3.0, "dinner", True, "grains"),
    ("Grilled Veg Sandwich", "1 sandwich", 280, 9.0, 38.0, 10.0, 4.0, "snack", True, "grains"),
    ("Peanut Butter Sandwich", "1 sandwich", 320, 11.0, 36.0, 15.0, 4.5, "snack", True, "snack"),
    ("Sprouts Salad", "1 bowl (150g)", 160, 10.0, 24.0, 2.0, 6.0, "snack", True, "protein"),
    ("Garden Salad", "1 bowl (200g)", 90, 3.0, 12.0, 3.0, 4.0, "lunch", True, "vegetable"),
    ("Fruit Salad", "1 bowl (200g)", 130, 2.0, 30.0, 1.0, 4.0, "snack", True, "fruit"),
    ("Tomato Soup", "1 bowl (200g)", 130, 3.0, 22.0, 3.0, 2.5, "snack", True, "vegetable"),
    ("Sweet Corn Soup", "1 bowl (250g)", 150, 5.0, 26.0, 3.0, 2.0, "snack", True, "vegetable"),
    ("Boondi Raita", "1 bowl (150g)", 150, 5.0, 14.0, 8.0, 0.5, "lunch", True, "dairy"),
    ("Protein Shake (whey in water)", "1 glass", 130, 25.0, 3.0, 1.0, 0.0, "snack", True, "protein"),
    ("Protein Bar", "1 bar (60g)", 220, 15.0, 22.0, 8.0, 5.0, "snack", True, "snack"),
    ("Banana Milkshake", "1 glass (250ml)", 280, 9.0, 48.0, 6.0, 2.5, "snack", True, "beverage"),
    ("Mango Shake", "1 glass (250ml)", 240, 7.0, 42.0, 5.0, 2.0, "snack", True, "beverage"),
    # ── Regional combo plates ───────────────────────────────────────────────────
    ("Chole Bhature", "1 plate", 650, 15.0, 75.0, 30.0, 8.0, "lunch", True, "protein"),
    ("Dal Baati", "1 plate", 520, 14.0, 64.0, 22.0, 6.0, "lunch", True, "grains"),
    ("Litti Chokha", "1 plate", 380, 10.0, 60.0, 12.0, 8.0, "lunch", True, "grains"),
    # ── Sweets & desserts (snack slot) ─────────────────────────────────────────
    ("Gulab Jamun", "1 piece", 150, 2.0, 24.0, 5.0, 0.2, "snack", True, "snack"),
    ("Rasmalai", "1 piece", 180, 5.0, 24.0, 7.0, 0.3, "snack", True, "dairy"),
    ("Kheer", "1 bowl (200g)", 280, 7.0, 42.0, 9.0, 0.8, "snack", True, "dairy"),
    ("Jalebi", "2 pieces", 250, 3.0, 42.0, 11.0, 0.3, "snack", True, "snack"),
    ("Ice Cream (vanilla)", "1 scoop", 140, 2.0, 18.0, 7.0, 0.5, "snack", True, "dairy"),
    ("Chocolate Brownie", "1 piece", 240, 3.0, 34.0, 11.0, 1.5, "snack", True, "snack"),
    ("Chocolate Cake Slice", "1 slice", 350, 4.0, 48.0, 16.0, 2.0, "snack", True, "snack"),
]


class Command(BaseCommand):
    """Seed the global dish/meal catalogue."""

    help = (
        "Populates the global dish/meal catalogue (120+ Indian and standard "
        "dishes with macros and meal-type tags). Idempotent; safe to re-run."
    )

    def add_arguments(self, parser: object) -> None:
        """Declare the ``--reset`` flag.

        Args:
            parser: The argparse-style argument parser.
        """
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete global seeded dishes (is_dish=True, tenant NULL) before seeding.",
        )

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        """Execute the seeding process.

        Args:
            *args: Positional arguments passed by Django.
            **options: Keyword options passed by Django.
        """
        if options.get("reset"):
            deleted, _ = FoodItem.objects.filter(
                is_dish=True,
                tenant__isnull=True,
            ).delete()
            self.stdout.write(f"Deleted {deleted} seeded dishes.")

        created = 0
        skipped = 0
        for name, serving, cal, pro, carb, fat, fiber, meal_type, is_veg, group in _DISH_DATA:
            _, was_created = FoodItem.objects.get_or_create(
                name=name,
                defaults={
                    "tenant": None,
                    "serving_size": serving,
                    "calories": cal,
                    "protein": pro,
                    "carbs": carb,
                    "fat": fat,
                    "fiber": fiber,
                    "meal_type": meal_type,
                    "is_veg": is_veg,
                    "food_group": group,
                    "is_dish": True,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write("Dishes per meal type:")
        for meal_type in FoodItem.MealType.choices:
            count = FoodItem.objects.filter(is_dish=True, meal_type=meal_type[0]).count()
            self.stdout.write(f"  {meal_type[1]}: {count}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} dishes ({skipped} already present). "
                f"Dish catalogue size: {FoodItem.objects.filter(is_dish=True).count()}. "
                f"Total food items: {FoodItem.objects.count()}.",
            ),
        )
