# Report — Ticket #89: Seed meals/dishes catalogue + create-dish flow

**Commit:** `f625c8f` → pushed `origin/develop`
**Branch:** `develop` (backend lane; FE piece included — it was small)

## Scoping decision (explicit, as required)

| Item type | Scope | Rationale |
|---|---|---|
| Seeded dish/meal catalogue | **Global** (`FoodItem.tenant = NULL`) | Nutrition of a butter chicken is identical for every gym; global rows avoid duplicating 134 dishes × N tenants and the seed runs **once per platform**. |
| Dishes created via API | **Tenant-scoped** (`FoodItem.tenant = request tenant`) | Each gym's custom dishes stay private; creating never leaks into other tenants' catalogues. |

- Visibility rule everywhere: **global ∪ own tenant** (`FoodItem.visible_to(tenant)`; `None` tenant → global only, e.g. platform admin).
- Uniqueness: case-insensitive name unique **among global rows**, and unique **within each tenant** for customs — two partial `UniqueConstraint`s on `Lower("name")` replace the old single global `unique=True`. A tenant cannot shadow a global name (dup validation covers global ∪ own tenant).
- Migration `0004` is **additive only**: new nullable FK, new nullable tag, new boolean, validators, new constraints. No columns dropped, no data touched.

## Model changes — `FoodItem` (table `diet_food_items`)

New fields:
- `tenant` — nullable FK → `tenants.Tenant` (`related_name="custom_food_items"`); `NULL` = global catalogue.
- `meal_type` — nullable tag: `breakfast | lunch | snack | dinner` (NULL = ingredient / any-time). Desserts, soups and shakes are tagged `snack` as the closest natural slot, so every seeded dish carries a slot.
- `is_dish` — boolean, default `False`; `True` for the seeded catalogue and API-created dishes, `False` for raw ingredients — lets #90/#94 query dishes precisely.

Macro numeric bounds (model validators, enforced by DRF + `full_clean`):
- `calories` 0–3000, `protein` 0–300, `carbs` 0–500, `fat` 0–300, `fiber` 0–200, `glycemic_index` 0–100.

## API (additive contract)

- **`POST /api/v1/food-items/`** — the create-dish provision (existing endpoint, hardened). Request tenant is attached server-side (`serializer.save(tenant=request.tenant)`); platform admins (no tenant) create global rows. Validation: case-insensitive duplicate name within visible scope → 400; macro bounds → 400; unknown `meal_type` → 400. Staff roles only (`diets.create_diet`, unchanged).
- **`GET /api/v1/food-items/`** — now returns global + own tenant's customs (was: all rows, which after custom dishes would have leaked cross-tenant). New filters: `meal_type=`, `is_dish=` (plus existing `search`, `food_group`, `is_veg`).
- `FoodItemSerializer` now exposes `tenant` (read-only), `meal_type`, `is_dish`.
- Tenant-isolation hardening in the blast radius: `DietMealSerializer.food_item` is restricted to visible items, so a gym cannot attach another gym's custom dish to a meal. (`DietRolePermission` no longer misreads NULL-tenant global rows as foreign tenants — update/delete of global items by tenant staff remains possible as before; see follow-ups.)

## Seed — `python manage.py seed_dishes`

Idempotent (`get_or_create` on name, global rows only), `--reset` deletes only global seeded dishes (never tenant customs). Verified run:

```
Seeded 134 dishes (0 already present). Dish catalogue size: 134. Total food items: 248.
Re-run: Seeded 0 dishes (134 already present).
```

- Meal-slot coverage: **breakfast 36 / lunch 39 / snack 37 / dinner 22** (134 total; brief asked 100–150).
- Content: Indian-heavy (~100: idli/dosa/poha/parathas, dals, paneer mains, biryanis, chaat, regional plates like dal baati & litti chokha) + standard/Western (~35: salads, pasta, burgers, momos, protein shakes/bars). All with realistic per-serving kcal/protein/carbs/fat/fiber, `serving_size` unit ("1 bowl (200g)", "2 pieces", …), veg flag, food group by dominant component.
- Zero case-insensitive name collisions within the dish list and against the existing `seed_food_items` catalogue (asserted by test).
- Wired into `qa_seed` base setup (`after seed_food_items`). Global rows mean **no per-tenant seeding is needed** — every existing and future tenant sees the catalogue immediately.

## Frontend (small piece — it was indeed trivial given existing infra)

- `AddFoodItemForm` component + "Add dish" card on `/diet/food-items` (staff-gated, hidden for customers): name, serving, macros, food group, optional meal slot, veg toggle; client-side required/non-negative validation, API errors surfaced.
- `FoodItem`/`FoodItemFormData` types gained optional `meal_type`/`is_dish`.

## Test evidence

- Backend: **30 new tests** (model scoping/constraints, serializer dup-name + bounds, API tenant-scoping/visibility/filters/400s, cross-tenant meal guard, seed idempotency/data hygiene). Diet suite **86 green**; full suite **1616 passed**, coverage **85%** (CI gate 80%); `flake8 . --count --show-source --statistics` → **0**. Two `apps/attendance/test_auto_checkout.py` failures are **pre-existing flakes** — verified failing on the clean tree (`git stash` run), unrelated to this work.
- Frontend: **7 new Jest tests** for the form; suite **708 passed / 55 suites**, `tsc --noEmit` clean, no new lint errors.

## Follow-ups (out of scope, noted)

1. Tenant staff can still **edit/delete global catalogue rows** (pre-existing behavior). Consider restricting global-row mutations to platform admin so gyms can't change shared macros platform-wide.
2. `DietDayWriteSerializer.diet_plan` PK field still accepts any tenant's plan (`DietPlan.objects.all()`) — pre-existing cross-tenant gap on diet-days, belongs with #90's plan-builder work.
3. FE catalogue page doesn't yet surface `meal_type`/`is_dish` filters or the global-vs-custom badge — rides the #90/#94 meal-plan waves.
