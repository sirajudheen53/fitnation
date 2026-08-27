"""Seed the marketplace catalog with sample products.

Usage::

    python manage.py seed_marketplace [--tenant <tenant_id>] [--reset]

Populates sample products across Supplements, Equipment, Apparel, and
Accessories categories. Products and categories are tenant-scoped.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.marketplace.models import Inventory, Product, ProductCategory
from apps.tenants.models import Tenant

_PRODUCT_DATA = [
    # ── Supplements ────────────────────────────────────────────────────────────
    {
        "name": "Whey Protein Powder (Chocolate, 1kg)",
        "category": "supplements",
        "slug": "whey-protein-powder-chocolate-1kg",
        "description": "Premium whey protein isolate blend with 25g protein per serving.",
        "price": "2999.00",
        "compare_price": "3499.00",
        "sku": "SUP-WHEY-CHOC-1KG",
        "barcode": "8901234500011",
        "brand": "MuscleFuel",
        "is_digital": False,
        "stock": 120,
        "image_url": "https://example.com/products/whey-chocolate.jpg",
    },
    {
        "name": "Creatine Monohydrate (300g)",
        "category": "supplements",
        "slug": "creatine-monohydrate-300g",
        "description": "Micronized creatine monohydrate for strength and power output.",
        "price": "899.00",
        "compare_price": None,
        "sku": "SUP-CREATINE-300G",
        "barcode": "8901234500028",
        "brand": "MuscleFuel",
        "is_digital": False,
        "stock": 200,
        "image_url": "https://example.com/products/creatine.jpg",
    },
    {
        "name": "BCAA Powder (Blueberry, 250g)",
        "category": "supplements",
        "slug": "bcaa-powder-blueberry-250g",
        "description": "Branch chain amino acids to support recovery during training.",
        "price": "1299.00",
        "compare_price": "1599.00",
        "sku": "SUP-BCAA-BB-250G",
        "barcode": "8901234502015",
        "brand": "PeakPerformance",
        "is_digital": False,
        "stock": 45,
        "image_url": "https://example.com/products/bcaa.jpg",
    },
    # ── Equipment ──────────────────────────────────────────────────────────────
    {
        "name": "Adjustable Dumbbell Set (2.5-25kg)",
        "category": "equipment",
        "slug": "adjustable-dumbbell-set-25kg",
        "description": "Space-saving adjustable dumbbells covering a full 2.5-25kg range.",
        "price": "8999.00",
        "compare_price": "10999.00",
        "sku": "EQP-DUMB-ADJ-25KG",
        "barcode": "8901234503012",
        "brand": "IronPro",
        "is_digital": False,
        "stock": 15,
        "image_url": "https://example.com/products/dumbbells.jpg",
    },
    {
        "name": "Resistance Bands Set (5-pack)",
        "category": "equipment",
        "slug": "resistance-bands-set-5pc",
        "description": "Five color-coded latex resistance bands with varying tension.",
        "price": "699.00",
        "compare_price": None,
        "sku": "FGQ-BAND-5PC",
        "barcode": "8901234503022",
        "brand": "FlexGear",
        "is_digital": False,
        "stock": 80,
        "image_url": "https://example.com/products/bands.jpg",
    },
    # ── Apparel ────────────────────────────────────────────────────────────────
    {
        "name": "Men's Performance Training Tee",
        "category": "apparel",
        "slug": "mens-performance-training-tee",
        "description": "Moisture-wicking training tee with four-way stretch fabric.",
        "price": "1499.00",
        "compare_price": "1799.00",
        "sku": "APP-TEE-M-BLACK",
        "barcode": "8901234504023",
        "brand": "IronThread",
        "is_digital": False,
        "stock": 150,
        "image_url": "https://example.com/products/training-tee.jpg",
    },
    {
        "name": "Women's High-Waist Yoga Leggings",
        "category": "apparel",
        "slug": "womens-high-waist-yoga-leggings",
        "description": "Squat-proof high-waist leggings with hidden pocket.",
        "price": "1799.00",
        "compare_price": "2199.00",
        "sku": "APP-LEG-W-NVY",
        "barcode": "8901234505025",
        "brand": "FlexGear",
        "is_digital": False,
        "stock": 60,
        "image_url": "https://example.com/products/leggings.jpg",
    },
    # ── Accessories ────────────────────────────────────────────────────────────
    {
        "name": "Premium Yoga Mat (6mm)",
        "category": "accessories",
        "slug": "premium-yoga-mat-6mm",
        "description": "Extra-thick non-slip TPE yoga mat with carry strap.",
        "price": "999.00",
        "compare_price": "1299.00",
        "sku": "ACC-YOGA-6MM",
        "barcode": "8901234506022",
        "brand": "ZenFit",
        "is_digital": False,
        "stock": 90,
        "image_url": "https://example.com/products/yoga-mat.jpg",
    },
    {
        "name": "Insulated Steel Water Bottle (1L)",
        "category": "accessories",
        "slug": "insulated-steel-water-bottle-1l",
        "description": "Vacuum-insulated steel bottle keeps drinks cold for 24 hours.",
        "price": "799.00",
        "compare_price": None,
        "sku": "ACC-BOTTLE-1L",
        "barcode": "8901234507029",
        "brand": "ZenPulse",
        "is_digital": False,
        "stock": 110,
        "image_url": "https://example.com/products/bottle.jpg",
    },
    {
        "name": "Premium Workout Plan (Digital)",
        "category": "accessories",
        "slug": "premium-workout-plan-digital",
        "description": "12-week progressive workout plan delivered digitally.",
        "price": "499.00",
        "compare_price": "999.00",
        "sku": "DIG-PLAN-12WK",
        "barcode": "",
        "brand": "MuscleFuel",
        "is_digital": True,
        "stock": 1000,
        "image_url": "https://example.com/products/workout-plan.jpg",
    },
]

_CATEGORY_DATA = [
    {
        "slug": "supplements",
        "name": "Supplements",
        "description": "Protein, amino acids, and performance nutrition.",
    },
    {
        "slug": "equipment",
        "name": "Equipment",
        "description": "Dumbbells, bands, and home gym gear.",
    },
    {
        "slug": "apparel",
        "name": "Apparel",
        "description": "Training wear and fitness clothing.",
    },
    {
        "slug": "accessories",
        "name": "Accessories",
        "description": "Mats, bottles, and training accessories.",
    },
]


class Command(BaseCommand):
    """Seed the marketplace product catalog with sample data."""

    help = "Populate the marketplace catalog with sample products."

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--tenant",
            type=int,
            help="Tenant ID to seed products for. Defaults to the first tenant.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing products and categories for the target tenant before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):  # noqa: ARG002
        """Run the seed command."""
        tenant_id = options.get("tenant")
        if tenant_id is None:
            tenant = Tenant.objects.order_by("id").first()
            if tenant is None:
                raise CommandError("No tenant found. Create a tenant first.")
        else:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist as exc:
                raise CommandError(f"Tenant with id {tenant_id} does not exist.") from exc

        if options.get("reset"):
            Product.objects.filter(tenant=tenant).delete()
            ProductCategory.objects.filter(tenant=tenant).delete()

        categories = self._get_categories(tenant)

        created = 0
        for item in _PRODUCT_DATA:
            category = categories[item["category"]]
            product, was_created = Product.objects.get_or_create(
                tenant=tenant,
                slug=item["slug"],
                defaults={
                    "category": category,
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "price": item["price"],
                    "compare_price": item.get("compare_price"),
                    "sku": item.get("sku", ""),
                    "barcode": item.get("barcode", ""),
                    "brand": item.get("brand", ""),
                    "status": Product.Status.ACTIVE,
                    "is_digital": item.get("is_digital", False),
                },
            )
            Inventory.objects.get_or_create(
                tenant=tenant,
                product=product,
                defaults={"stock_quantity": item.get("stock", 0)},
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} products for tenant '{tenant.name}' " f"across {len(categories)} categories.",
            )
        )

    def _get_categories(self, tenant: Tenant) -> dict:
        """Return a mapping of slug to category, creating defaults if absent."""
        result = {}
        for data in _CATEGORY_DATA:
            category, _ = ProductCategory.objects.get_or_create(
                tenant=tenant,
                slug=data["slug"],
                defaults=data,
            )
            result[data["slug"]] = category
        return result
