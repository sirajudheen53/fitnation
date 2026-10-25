"""Exercise library services (catalogue seeding)."""

from __future__ import annotations

from django.db import transaction

from apps.exercises.catalogue import DEFAULT_CATEGORIES, EXERCISE_CATALOGUE
from apps.exercises.models import Exercise, ExerciseCategory
from apps.tenants.models import Tenant


def seed_library_for_tenant(tenant: Tenant) -> dict[str, int]:
    """Populate the common exercise catalogue for one tenant, idempotently.

    Get-or-update semantics keyed on the exercise name within the tenant:
    catalogue rows are upserted in place (only fields that actually drifted
    are written back), default categories are created when missing, and
    anything the gym created themselves — extra categories, custom exercises —
    is never touched or deleted. Safe to run repeatedly.

    Args:
        tenant: The tenant to seed for.

    Returns:
        ``{"categories_created", "exercises_created", "exercises_updated"}``.
    """
    result = {"categories_created": 0, "exercises_created": 0, "exercises_updated": 0}
    with transaction.atomic():
        categories = {c.slug: c for c in ExerciseCategory.objects.filter(tenant=tenant, slug__in=DEFAULT_CATEGORIES)}
        for slug, data in DEFAULT_CATEGORIES.items():
            if slug not in categories:
                category, _ = ExerciseCategory.objects.get_or_create(
                    tenant=tenant,
                    slug=slug,
                    defaults=data,
                )
                categories[slug] = category
                result["categories_created"] += 1

        names = [item["name"] for item in EXERCISE_CATALOGUE]
        existing = {e.name: e for e in Exercise.objects.filter(tenant=tenant, name__in=names)}
        to_create: list[Exercise] = []
        for item in EXERCISE_CATALOGUE:
            try:
                category = categories[item["category"]]
            except KeyError as exc:
                raise ValueError(
                    f"Catalogue exercise '{item['name']}' references unknown category '{item['category']}'.",
                ) from exc
            fields = {
                "description": item.get("description", ""),
                "category": category,
                "muscle_groups": item["muscle_groups"],
                "equipment_needed": item.get("equipment_needed", []),
                "difficulty": item["difficulty"],
                "instructions": item.get("instructions", []),
                "media_url": item.get("media_url"),
                "tips": item.get("tips", ""),
                "contraindications": item.get("contraindications", ""),
            }
            exercise = existing.pop(item["name"], None)
            if exercise is None:
                to_create.append(Exercise(tenant=tenant, name=item["name"], **fields))
                continue
            changed = [field for field, value in fields.items() if getattr(exercise, field) != value]
            if changed:
                for field in changed:
                    setattr(exercise, field, fields[field])
                exercise.save(update_fields=changed + ["updated_at"])
                result["exercises_updated"] += 1
        Exercise.objects.bulk_create(to_create, batch_size=200)
        result["exercises_created"] = len(to_create)
    return result
