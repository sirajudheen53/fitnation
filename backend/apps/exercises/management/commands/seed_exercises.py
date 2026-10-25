"""Seed the exercise library with common exercises.

Usage::

    python manage.py seed_exercises [--tenant <tenant_id>] [--reset]

Populates the common catalogue (100 exercises across Strength, Cardio,
Flexibility, and Mobility categories) for the tenant using get-or-update
semantics: existing rows are refreshed, tenant-created rows are never
deleted. See :func:`apps.exercises.services.seed_library_for_tenant`.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.exercises.catalogue import DEFAULT_CATEGORIES, EXERCISE_CATALOGUE
from apps.exercises.models import Exercise, ExerciseCategory
from apps.exercises.services import seed_library_for_tenant
from apps.tenants.models import Tenant


class Command(BaseCommand):
    """Seed the exercise library."""

    help = "Populate the exercise library with common exercises."

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--tenant",
            type=int,
            help="Tenant ID to seed exercises for. Defaults to the first tenant.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing exercises and categories for the target tenant before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
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
            Exercise.objects.filter(tenant=tenant).delete()
            ExerciseCategory.objects.filter(tenant=tenant).delete()

        result = seed_library_for_tenant(tenant)

        catalogued = self._catalogued_per_category()
        rows = {c.slug: c.exercises.count() for c in ExerciseCategory.objects.filter(tenant=tenant)}
        for slug, name in ((slug, data["name"]) for slug, data in DEFAULT_CATEGORIES.items()):
            self.stdout.write(f"  {name}: {catalogued[slug]} catalogued / {rows.get(slug, 0)} in library")
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded tenant '{tenant.name}': "
                f"{result['exercises_created']} created, {result['exercises_updated']} updated, "
                f"{result['categories_created']} categories created "
                f"(catalogue size {len(EXERCISE_CATALOGUE)}).",
            )
        )

    def _catalogued_per_category(self) -> dict[str, int]:
        """Count catalogue entries per category slug."""
        counts: dict[str, int] = {}
        for item in EXERCISE_CATALOGUE:
            counts[item["category"]] = counts.get(item["category"], 0) + 1
        return counts
