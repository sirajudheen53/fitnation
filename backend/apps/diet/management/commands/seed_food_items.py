"""Seed the global food catalog with common Indian food items.

Usage::

    python manage.py seed_food_items [--reset]

Populates 100+ common Indian food items with nutrition data. Food items are
global (not tenant-scoped), so the command runs once per platform.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.diet.models import FoodItem

# name, serving_size, calories, protein, carbs, fat, fiber, glycemic_index, food_group, is_veg
_FOOD_DATA: list[tuple] = [
    # ── Grains & Rice ──────────────────────────────────────────────────────────
    ("White Rice (cooked)", "100g", 130, 2.7, 28.2, 0.3, 0.4, 73, "grains", True),
    ("Brown Rice (cooked)", "100g", 111, 2.6, 23.0, 0.9, 1.8, 50, "grains", True),
    ("Basmati Rice (cooked)", "100g", 121, 3.1, 26.2, 0.4, 0.7, 58, "grains", True),
    ("Roti (wheat chapati)", "1 piece", 106, 3.1, 17.9, 2.7, 2.0, 55, "grains", True),
    ("Whole Wheat Chapati", "1 piece", 104, 3.3, 17.5, 2.6, 2.2, 55, "grains", True),
    ("Naan", "1 piece", 262, 9.0, 45.0, 5.0, 2.0, 70, "grains", True),
    ("Paratha (plain)", "1 piece", 250, 6.0, 35.0, 10.0, 2.0, 72, "grains", True),
    ("Poha (flattened rice)", "100g", 225, 4.6, 50.0, 0.6, 2.5, 70, "grains", True),
    ("Oats (rolled)", "40g", 150, 5.5, 27.0, 3.0, 4.0, 55, "grains", True),
    ("Daliya (broken wheat)", "100g", 340, 13.0, 72.0, 2.0, 12.0, 55, "grains", True),
    ("Quinoa (cooked)", "100g", 120, 4.4, 21.3, 1.9, 2.8, 53, "grains", True),
    ("Millet (bajra)", "100g", 361, 11.0, 67.0, 5.0, 11.0, 55, "grains", True),
    ("Jowar (sorghum)", "100g", 348, 10.4, 75.0, 3.1, 6.7, 62, "grains", True),
    ("Ragi (finger millet)", "100g", 328, 7.3, 72.0, 1.3, 3.6, 55, "grains", True),
    ("Idli (steamed)", "1 piece", 58, 2.0, 11.5, 0.4, 1.2, 65, "grains", True),
    ("Dosa (plain)", "1 piece", 121, 3.0, 23.0, 2.0, 1.5, 60, "grains", True),
    ("Uttapam", "1 piece", 200, 5.0, 33.0, 6.0, 3.0, 62, "grains", True),
    ("Wheat Bread", "1 slice", 67, 3.0, 12.0, 1.0, 1.5, 55, "grains", True),
    ("Whole Wheat Pasta (cooked)", "100g", 157, 5.5, 30.0, 1.5, 3.0, 45, "grains", True),
    ("Corn (boiled)", "100g", 96, 3.4, 21.0, 1.5, 2.4, 52, "grains", True),
    ("Rice Pulao", "100g", 150, 3.0, 28.0, 3.0, 1.0, 70, "grains", True),
    # ── Protein ─────────────────────────────────────────────────────────────────
    ("Toor Dal (cooked)", "100g", 110, 7.0, 19.0, 1.5, 6.0, 30, "protein", True),
    ("Moong Dal (cooked)", "100g", 105, 7.0, 18.0, 1.0, 7.0, 35, "protein", True),
    ("Masoor Dal (cooked)", "100g", 116, 9.0, 19.0, 0.4, 7.0, 25, "protein", True),
    ("Chana Dal (cooked)", "100g", 120, 8.0, 20.0, 2.0, 5.0, 30, "protein", True),
    ("Rajma (cooked)", "100g", 125, 8.0, 22.0, 0.5, 7.0, 30, "protein", True),
    ("Chole (chickpea curry)", "100g", 150, 8.0, 22.0, 4.0, 7.0, 35, "protein", True),
    ("Lobia (black-eyed peas)", "100g", 130, 8.0, 23.0, 0.5, 6.0, 40, "protein", True),
    ("Soya Chunks (cooked)", "100g", 140, 15.0, 8.0, 5.0, 4.0, 30, "protein", True),
    ("Paneer (cottage cheese)", "100g", 265, 18.0, 4.0, 21.0, 0.0, 27, "protein", True),
    ("Tofu", "100g", 76, 8.0, 1.9, 4.8, 0.3, 15, "protein", True),
    ("Soya Milk", "1 cup", 80, 7.0, 4.0, 4.0, 1.0, 30, "protein", True),
    ("Green Peas (boiled)", "100g", 81, 5.4, 14.5, 0.4, 5.7, 48, "protein", True),
    ("Black Chana (cooked)", "100g", 164, 9.0, 28.0, 3.0, 8.0, 30, "protein", True),
    ("Chicken Breast (cooked)", "100g", 165, 31.0, 0.0, 3.6, 0.0, 0, "protein", False),
    ("Chicken Thigh (cooked)", "100g", 209, 26.0, 0.0, 11.0, 0.0, 0, "protein", False),
    ("Egg (whole, boiled)", "1 piece", 72, 6.3, 0.4, 4.8, 0.0, 0, "protein", False),
    ("Egg White", "1 piece", 17, 3.6, 0.2, 0.1, 0.0, 0, "protein", False),
    ("Fish (Rohu, cooked)", "100g", 110, 18.0, 0.0, 4.0, 0.0, 0, "protein", False),
    ("Salmon (cooked)", "100g", 206, 22.0, 0.0, 13.0, 0.0, 0, "protein", False),
    ("Mutton (cooked)", "100g", 250, 25.0, 0.0, 18.0, 0.0, 0, "protein", False),
    ("Prawns (cooked)", "100g", 99, 24.0, 0.2, 0.3, 0.0, 0, "protein", False),
    # ── Vegetables ───────────────────────────────────────────────────────────────
    ("Spinach (palak)", "100g", 23, 2.9, 3.6, 0.4, 2.2, 40, "vegetable", True),
    ("Okra (bhindi)", "100g", 33, 1.9, 7.5, 0.2, 3.2, 32, "vegetable", True),
    ("Cauliflower (gobi)", "100g", 25, 1.9, 5.0, 0.3, 2.0, 15, "vegetable", True),
    ("Eggplant (baingan)", "100g", 25, 1.0, 5.9, 0.2, 3.0, 20, "vegetable", True),
    ("Pumpkin (kaddu)", "100g", 26, 1.0, 6.5, 0.1, 0.5, 75, "vegetable", True),
    ("Cabbage", "100g", 25, 1.3, 5.8, 0.1, 2.5, 10, "vegetable", True),
    ("Bottle gourd (lauki)", "100g", 15, 0.6, 3.4, 0.0, 0.5, 15, "vegetable", True),
    ("Bitter gourd (karela)", "100g", 17, 1.0, 3.7, 0.2, 2.0, 25, "vegetable", True),
    ("Ridge gourd (tori)", "100g", 18, 0.5, 4.0, 0.1, 1.0, 20, "vegetable", True),
    ("Broccoli", "100g", 34, 2.8, 6.6, 0.4, 2.5, 15, "vegetable", True),
    ("Carrot", "100g", 41, 0.9, 9.6, 0.2, 2.8, 39, "vegetable", True),
    ("Beetroot", "100g", 43, 1.6, 9.6, 0.2, 2.8, 64, "vegetable", True),
    ("Cucumber", "100g", 15, 0.7, 3.6, 0.1, 0.5, 15, "vegetable", True),
    ("Tomato", "100g", 18, 0.9, 3.9, 0.2, 1.2, 30, "vegetable", True),
    ("Onion", "100g", 40, 1.1, 9.3, 0.1, 1.7, 25, "vegetable", True),
    ("Capsicum (bell pepper)", "100g", 26, 1.0, 6.0, 0.3, 2.0, 25, "vegetable", True),
    ("Fenugreek leaves (methi)", "100g", 30, 3.0, 6.0, 0.3, 2.0, 30, "vegetable", True),
    ("Green Beans", "100g", 31, 1.8, 6.9, 0.2, 2.5, 30, "vegetable", True),
    ("Zucchini", "100g", 17, 1.2, 3.1, 0.3, 1.0, 15, "vegetable", True),
    ("Sweet Potato", "100g", 86, 1.6, 20.1, 0.1, 3.0, 54, "vegetable", True),
    ("Potato (boiled)", "100g", 87, 1.9, 20.1, 0.1, 1.8, 78, "vegetable", True),
    # ── Fruits ───────────────────────────────────────────────────────────────────
    ("Apple", "1 medium", 95, 0.5, 25.0, 0.3, 4.4, 36, "fruit", True),
    ("Banana", "1 medium", 105, 1.3, 27.0, 0.4, 3.1, 51, "fruit", True),
    ("Orange", "1 medium", 62, 1.2, 15.4, 0.2, 3.1, 40, "fruit", True),
    ("Grapes", "100g", 69, 0.7, 18.0, 0.2, 0.9, 53, "fruit", True),
    ("Mango", "100g", 60, 0.8, 15.0, 0.4, 1.6, 56, "fruit", True),
    ("Papaya", "100g", 43, 0.5, 10.8, 0.3, 1.7, 56, "fruit", True),
    ("Watermelon", "100g", 30, 0.6, 7.6, 0.2, 0.4, 72, "fruit", True),
    ("Guava", "100g", 68, 2.6, 14.3, 1.0, 5.4, 32, "fruit", True),
    ("Pomegranate", "100g", 83, 1.7, 18.7, 1.2, 4.0, 53, "fruit", True),
    ("Pineapple", "100g", 50, 0.5, 13.1, 0.1, 1.4, 59, "fruit", True),
    ("Pear", "1 medium", 101, 0.6, 27.1, 0.2, 5.5, 35, "fruit", True),
    ("Strawberry", "100g", 32, 0.7, 7.7, 0.3, 2.0, 40, "fruit", True),
    ("Indian Gooseberry (amla)", "100g", 58, 0.9, 13.7, 0.1, 4.0, 30, "fruit", True),
    ("Chikoo (sapota)", "100g", 83, 0.4, 19.9, 1.1, 5.3, 40, "fruit", True),
    ("Lychee", "100g", 66, 0.8, 16.5, 0.4, 1.3, 52, "fruit", True),
    ("Coconut (fresh)", "100g", 354, 3.3, 15.2, 33.5, 9.0, 50, "fruit", True),
    # ── Dairy ────────────────────────────────────────────────────────────────────
    ("Milk (toned, 3% fat)", "1 cup", 121, 8.1, 11.0, 4.7, 0.0, 30, "dairy", True),
    ("Milk (full cream)", "1 cup", 150, 7.7, 12.0, 8.5, 0.0, 30, "dairy", True),
    ("Milk (skimmed)", "1 cup", 83, 8.4, 12.0, 0.2, 0.0, 30, "dairy", True),
    ("Curd (dahi)", "100g", 98, 11.0, 3.4, 4.3, 0.0, 30, "dairy", True),
    ("Greek Yogurt", "100g", 59, 10.0, 3.6, 0.4, 0.0, 20, "dairy", True),
    ("Cheese (processed)", "100g", 324, 19.0, 2.0, 27.0, 0.0, 30, "dairy", True),
    ("Butter", "1 tbsp", 100, 0.1, 0.0, 11.3, 0.0, 0, "dairy", True),
    ("Lassi (sweet)", "1 cup", 150, 6.0, 22.0, 4.0, 0.0, 40, "dairy", True),
    ("Chaach (buttermilk)", "1 cup", 40, 3.0, 5.0, 1.0, 0.0, 20, "dairy", True),
    # ── Fats & Oils ──────────────────────────────────────────────────────────────
    ("Ghee (clarified butter)", "1 tbsp", 120, 0.0, 0.0, 13.6, 0.0, 0, "fat", True),
    ("Olive Oil", "1 tbsp", 119, 0.0, 0.0, 13.5, 0.0, 0, "fat", True),
    ("Groundnut Oil", "1 tbsp", 120, 0.0, 0.0, 13.5, 0.0, 0, "fat", True),
    ("Coconut Oil", "1 tbsp", 121, 0.0, 0.0, 13.6, 0.0, 0, "fat", True),
    ("Mustard Oil", "1 tbsp", 124, 0.0, 0.0, 14.0, 0.0, 0, "fat", True),
    ("Almonds", "100g", 579, 21.2, 21.6, 49.9, 12.5, 15, "fat", True),
    ("Walnuts", "100g", 654, 15.2, 13.7, 65.2, 6.7, 15, "fat", True),
    ("Peanuts", "100g", 567, 25.8, 16.1, 49.2, 8.5, 13, "fat", True),
    ("Peanut Butter", "1 tbsp", 94, 4.0, 3.5, 8.0, 1.0, 14, "fat", True),
    ("Sesame Seeds", "100g", 573, 17.7, 23.4, 49.7, 11.8, 15, "fat", True),
    ("Flax Seeds", "100g", 534, 18.3, 28.9, 42.2, 27.3, 15, "fat", True),
    ("Chia Seeds", "100g", 486, 16.5, 42.1, 30.7, 34.4, 15, "fat", True),
    # ── Snacks ───────────────────────────────────────────────────────────────────
    ("Roasted Chana", "100g", 372, 22.5, 63.9, 5.9, 12.0, 28, "snack", True),
    ("Makhana (fox nuts)", "100g", 347, 9.7, 76.9, 0.1, 5.0, 50, "snack", True),
    ("Murmura (puffed rice)", "100g", 300, 8.0, 80.0, 1.0, 3.0, 55, "snack", True),
    ("Bhel Puri", "1 cup", 150, 3.0, 25.0, 5.0, 2.0, 60, "snack", True),
    ("Samosa (potato)", "1 piece", 260, 4.0, 30.0, 15.0, 1.5, 60, "snack", False),
    ("Upma", "100g", 150, 4.0, 25.0, 4.0, 2.0, 60, "snack", True),
    ("Roasted Makhana", "30g", 100, 3.0, 22.0, 0.1, 1.5, 50, "snack", True),
    # ── Beverages ────────────────────────────────────────────────────────────────
    ("Green Tea (unsweetened)", "1 cup", 2, 0.0, 0.4, 0.0, 0.0, 0, "beverage", True),
    ("Black Coffee (no sugar)", "1 cup", 2, 0.3, 0.0, 0.0, 0.0, 0, "beverage", True),
    ("Lemon Water", "1 glass", 10, 0.0, 2.5, 0.0, 0.1, 0, "beverage", True),
    ("Buttermilk (chaas)", "1 cup", 40, 3.5, 5.0, 1.0, 0.0, 20, "beverage", True),
    ("Coconut Water", "1 cup", 45, 2.0, 9.0, 0.5, 0.0, 0, "beverage", True),
    ("Vegetable Juice", "1 glass", 50, 2.0, 10.0, 0.2, 2.0, 30, "beverage", True),
    ("Fresh Orange Juice", "1 glass", 110, 2.0, 25.0, 0.5, 0.5, 45, "beverage", True),
]


class Command(BaseCommand):
    """Seed the global food item catalog."""

    help = "Populates the global food item catalog with common Indian foods."

    def add_arguments(self, parser: object) -> None:
        """Declare the ``--reset`` flag.

        Args:
            parser: The argparse-style argument parser.
        """
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing food items before seeding.",
        )

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        """Execute the seeding process.

        Args:
            *args: Positional arguments passed by Django.
            **options: Keyword options passed by Django.
        """
        reset = options.get("reset", False)
        if reset:
            deleted, _ = FoodItem.objects.all().delete()
            self.stdout.write(f"Deleted {deleted} existing food items.")

        created = 0
        skipped = 0
        for name, serving, cal, pro, carb, fat, fiber, gi, group, is_veg in _FOOD_DATA:
            _, was_created = FoodItem.objects.get_or_create(
                name=name,
                defaults={
                    "serving_size": serving,
                    "calories": cal,
                    "protein": pro,
                    "carbs": carb,
                    "fat": fat,
                    "fiber": fiber,
                    "glycemic_index": gi if gi else None,
                    "food_group": group,
                    "is_veg": is_veg,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} food items ({skipped} already present). "
                f"Total catalog size: {FoodItem.objects.count()}.",
            ),
        )
