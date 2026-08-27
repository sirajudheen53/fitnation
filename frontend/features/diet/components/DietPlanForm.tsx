"use client";

import { useMemo, useState } from "react";
import { Plus, Trash2, Apple, CalendarDays, UtensilsCrossed } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type {
  DietDay,
  DietDayFormData,
  DietGoal,
  DietMealFormData,
  DietPlan,
  DietPlanFormData,
  FoodItem,
  MealType,
} from "@/types/diet";
import { errorMessage } from "@/lib/api";
import {
  GOAL_LABELS,
  MEAL_TYPE_LABELS,
  mealNutrition,
  formatNumber,
} from "./nutritionHelpers";

const GOALS = Object.keys(GOAL_LABELS) as DietGoal[];
const MEAL_TYPES = Object.keys(MEAL_TYPE_LABELS) as MealType[];

interface DraftMeal extends DietMealFormData {
  food_item_name?: string;
  calories?: number;
  protein?: number;
  carbs?: number;
  fat?: number;
}

interface DraftDay {
  day_number: number;
  notes: string;
  meals: DraftMeal[];
}

interface DietPlanFormProps {
  plan?: DietPlan;
  foodItems: FoodItem[];
  submitLabel?: string;
  onSubmit: (data: DietPlanFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function DietPlanForm({
  plan,
  foodItems,
  submitLabel = "Save plan",
  onSubmit,
  error,
  loading = false,
}: DietPlanFormProps) {
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.description ?? "");
  const [goal, setGoal] = useState<DietGoal>(plan?.goal ?? "maintain");
  const [dailyCalories, setDailyCalories] = useState(plan?.daily_calories ?? 2000);
  const [proteinRatio, setProteinRatio] = useState(plan?.protein_ratio ?? 30);
  const [carbRatio, setCarbRatio] = useState(plan?.carb_ratio ?? 40);
  const [fatRatio, setFatRatio] = useState(plan?.fat_ratio ?? 30);
  const [durationDays, setDurationDays] = useState(plan?.duration_days ?? 7);
  const [isTemplate, setIsTemplate] = useState(plan?.is_template ?? false);
  const [days, setDays] = useState<DraftDay[]>(
    plan?.days.map((d: DietDay) => ({
      day_number: d.day_number,
      notes: d.notes ?? "",
      meals: d.meals.map((m) => ({
        meal_type: m.meal_type,
        food_item: m.food_item,
        food_item_name: m.food_item_name,
        quantity: m.quantity,
        calories: m.calories,
        protein: m.protein,
        carbs: m.carbs,
        fat: m.fat,
      })),
    })) ?? [],
  );

  // Meal draft state
  const [activeDay, setActiveDay] = useState<number>(0);
  const [mealType, setMealType] = useState<MealType>("breakfast");
  const [foodItemId, setFoodItemId] = useState<number | "">("");
  const [quantity, setQuantity] = useState(1);

  // Re-sync state when the `plan` prop changes (e.g. navigating between
  // edit pages) without re-mounting the form.
  const [prevPlan, setPrevPlan] = useState<DietPlan | undefined>(plan);
  if (plan !== prevPlan) {
    setPrevPlan(plan);
    if (plan) {
      setName(plan.name);
      setDescription(plan.description);
      setGoal(plan.goal);
      setDailyCalories(plan.daily_calories);
      setProteinRatio(plan.protein_ratio);
      setCarbRatio(plan.carb_ratio);
      setFatRatio(plan.fat_ratio);
      setDurationDays(plan.duration_days);
      setIsTemplate(plan.is_template);
      setDays(
        plan.days.map((d: DietDay) => ({
          day_number: d.day_number,
          notes: d.notes ?? "",
          meals: d.meals.map((m) => ({
            meal_type: m.meal_type,
            food_item: m.food_item,
            food_item_name: m.food_item_name,
            quantity: m.quantity,
            calories: m.calories,
            protein: m.protein,
            carbs: m.carbs,
            fat: m.fat,
          })),
        })),
      );
    }
  }

  const selectedFood = useMemo(
    () => foodItems.find((f) => f.id === Number(foodItemId)),
    [foodItems, foodItemId],
  );

  const addDay = () => {
    const nextNumber = days.length + 1;
    setDays((prev) => [...prev, { day_number: nextNumber, notes: "", meals: [] }]);
    setActiveDay(days.length);
  };

  const removeDay = (index: number) => {
    setDays((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.map((d, i) => ({ ...d, day_number: i + 1 }));
    });
    setActiveDay((prev) => Math.max(0, Math.min(prev, days.length - 2)));
  };

  const addMeal = () => {
    if (!selectedFood || foodItemId === "") return;
    const nutrition = mealNutrition(selectedFood, quantity);
    const meal: DraftMeal = {
      meal_type: mealType,
      food_item: selectedFood.id,
      food_item_name: selectedFood.name,
      quantity,
      ...nutrition,
    };
    setDays((prev) =>
      prev.map((d, i) => (i === activeDay ? { ...d, meals: [...d.meals, meal] } : d)),
    );
    setFoodItemId("");
    setQuantity(1);
  };

  const removeMeal = (dayIndex: number, mealIndex: number) => {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIndex
          ? { ...d, meals: d.meals.filter((_, mi) => mi !== mealIndex) }
          : d,
      ),
    );
  };

  const dayTotals = useMemo(
    () =>
      days.map((d) =>
        d.meals.reduce(
          (acc, m) => {
            acc.calories += m.calories ?? 0;
            acc.protein += m.protein ?? 0;
            acc.carbs += m.carbs ?? 0;
            acc.fat += m.fat ?? 0;
            return acc;
          },
          { calories: 0, protein: 0, carbs: 0, fat: 0 },
        ),
      ),
    [days],
  );

  const planTotals = useMemo(
    () =>
      dayTotals.reduce(
        (acc, t) => {
          acc.calories += t.calories;
          acc.protein += t.protein;
          acc.carbs += t.carbs;
          acc.fat += t.fat;
          return acc;
        },
        { calories: 0, protein: 0, carbs: 0, fat: 0 },
      ),
    [dayTotals],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (days.length === 0) return;
    const payload: DietPlanFormData = {
      name,
      description: description || undefined,
      goal,
      daily_calories: dailyCalories,
      protein_ratio: proteinRatio,
      carb_ratio: carbRatio,
      fat_ratio: fatRatio,
      duration_days: durationDays,
      is_template: isTemplate,
      days: days.map((d): DietDayFormData => ({
        day_number: d.day_number,
        notes: d.notes || undefined,
        meals: d.meals.map((m) => ({
          meal_type: m.meal_type,
          food_item: m.food_item,
          quantity: m.quantity,
        })),
      })),
    };
    void onSubmit(payload);
  };

  const activeDayData = days[activeDay];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      {/* Plan details */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Plan details</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input
            label="Plan name"
            placeholder="Lean Bulk 3000"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <div className="space-y-1.5">
            <label htmlFor="goal" className="block text-sm font-medium text-gray-700">
              Goal
            </label>
            <select
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value as DietGoal)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {GOALS.map((g) => (
                <option key={g} value={g}>
                  {GOAL_LABELS[g]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 space-y-1.5">
          <label htmlFor="description" className="block text-sm font-medium text-gray-700">
            Description
          </label>
          <textarea
            id="description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this plan for?"
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Input
            label="Daily calories"
            type="number"
            min="0"
            value={dailyCalories}
            onChange={(e) => setDailyCalories(Number(e.target.value))}
          />
          <Input
            label="Protein %"
            type="number"
            min="0"
            max="100"
            value={proteinRatio}
            onChange={(e) => setProteinRatio(Number(e.target.value))}
          />
          <Input
            label="Carbs %"
            type="number"
            min="0"
            max="100"
            value={carbRatio}
            onChange={(e) => setCarbRatio(Number(e.target.value))}
          />
          <Input
            label="Fat %"
            type="number"
            min="0"
            max="100"
            value={fatRatio}
            onChange={(e) => setFatRatio(Number(e.target.value))}
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input
            label="Duration (days)"
            type="number"
            min="1"
            value={durationDays}
            onChange={(e) => setDurationDays(Number(e.target.value))}
          />
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 p-4">
            <input
              type="checkbox"
              checked={isTemplate}
              onChange={(e) => setIsTemplate(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            />
            <span className="text-sm font-medium text-gray-700">Template plan</span>
          </label>
        </div>
      </div>

      {/* Day builder */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Days & meals</h2>
          <Button type="button" variant="outline" size="sm" onClick={addDay}>
            <Plus className="h-4 w-4" /> Add day
          </Button>
        </div>

        {days.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
            <CalendarDays className="mx-auto h-8 w-8 text-gray-300" />
            <p className="mt-2 text-sm text-gray-500">
              No days yet. Add a day to start building meals.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Day tabs */}
            <div className="flex flex-wrap gap-2">
              {days.map((d, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveDay(i)}
                  className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    i === activeDay
                      ? "bg-brand-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  Day {d.day_number}
                  <span className="text-xs opacity-70">
                    {formatNumber(dayTotals[i].calories)} kcal
                  </span>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      removeDay(i);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.stopPropagation();
                        removeDay(i);
                      }
                    }}
                    className="ml-1 rounded p-0.5 hover:bg-black/10"
                    aria-label={`Remove day ${d.day_number}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </span>
                </button>
              ))}
            </div>

            {activeDayData && (
              <div className="rounded-lg border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="font-medium text-gray-900">
                    Day {activeDayData.day_number}
                  </h3>
                  <span className="text-sm text-gray-500">
                    {formatNumber(dayTotals[activeDay].calories)} kcal total
                  </span>
                </div>

                {/* Meal add form */}
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <div className="space-y-1.5">
                    <label
                      htmlFor={`meal-type-${activeDay}`}
                      className="block text-xs font-medium text-gray-600"
                    >
                      Meal type
                    </label>
                    <select
                      id={`meal-type-${activeDay}`}
                      value={mealType}
                      onChange={(e) => setMealType(e.target.value as MealType)}
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    >
                      {MEAL_TYPES.map((mt) => (
                        <option key={mt} value={mt}>
                          {MEAL_TYPE_LABELS[mt]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label
                      htmlFor={`food-item-${activeDay}`}
                      className="block text-xs font-medium text-gray-600"
                    >
                      Food item
                    </label>
                    <select
                      id={`food-item-${activeDay}`}
                      value={foodItemId}
                      onChange={(e) =>
                        setFoodItemId(e.target.value ? Number(e.target.value) : "")
                      }
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    >
                      <option value="">Select food…</option>
                      {foodItems.map((f) => (
                        <option key={f.id} value={f.id}>
                          {f.name} ({f.serving_size})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label
                      htmlFor={`quantity-${activeDay}`}
                      className="block text-xs font-medium text-gray-600"
                    >
                      Quantity
                    </label>
                    <input
                      id={`quantity-${activeDay}`}
                      type="number"
                      min="0.1"
                      step="0.1"
                      value={quantity}
                      onChange={(e) => setQuantity(Number(e.target.value))}
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={addMeal}
                      disabled={!selectedFood}
                      className="w-full"
                    >
                      <Plus className="h-4 w-4" /> Add meal
                    </Button>
                  </div>
                </div>

                {selectedFood && (
                  <p className="mt-2 text-xs text-gray-500">
                    {selectedFood.name}: {formatNumber(selectedFood.calories)} kcal ×{" "}
                    {quantity} ={" "}
                    {formatNumber(selectedFood.calories * quantity)} kcal
                  </p>
                )}

                {/* Meals list */}
                {activeDayData.meals.length === 0 ? (
                  <p className="mt-4 text-sm text-gray-400">
                    No meals in this day yet.
                  </p>
                ) : (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-gray-100 text-xs uppercase text-gray-500">
                        <tr>
                          <th className="py-2 pr-3 font-medium">Meal</th>
                          <th className="py-2 pr-3 font-medium">Food</th>
                          <th className="py-2 pr-3 font-medium">Qty</th>
                          <th className="py-2 pr-3 font-medium">Cal</th>
                          <th className="py-2 pr-3 font-medium">Protein</th>
                          <th className="py-2 pr-3 font-medium">Carbs</th>
                          <th className="py-2 pr-3 font-medium">Fat</th>
                          <th className="py-2 text-right font-medium"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {activeDayData.meals.map((m, mi) => (
                          <tr key={mi}>
                            <td className="py-2 pr-3 text-gray-700">
                              {MEAL_TYPE_LABELS[m.meal_type] ?? m.meal_type}
                            </td>
                            <td className="py-2 pr-3 font-medium text-gray-900">
                              {m.food_item_name ?? `Food #${m.food_item}`}
                            </td>
                            <td className="py-2 pr-3 text-gray-600">{m.quantity}</td>
                            <td className="py-2 pr-3 text-gray-700">
                              {formatNumber(m.calories ?? 0)}
                            </td>
                            <td className="py-2 pr-3 text-gray-700">
                              {formatNumber(m.protein ?? 0)}g
                            </td>
                            <td className="py-2 pr-3 text-gray-700">
                              {formatNumber(m.carbs ?? 0)}g
                            </td>
                            <td className="py-2 pr-3 text-gray-700">
                              {formatNumber(m.fat ?? 0)}g
                            </td>
                            <td className="py-2 text-right">
                              <button
                                type="button"
                                onClick={() => removeMeal(activeDay, mi)}
                                className="rounded p-1.5 text-red-500 hover:bg-red-50"
                                aria-label="Remove meal"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Nutrition summary */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
          <UtensilsCrossed className="h-5 w-5 text-brand-600" /> Nutrition summary
        </h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { label: "Total calories", value: `${formatNumber(planTotals.calories)} kcal` },
            { label: "Total protein", value: `${formatNumber(planTotals.protein)} g` },
            { label: "Total carbs", value: `${formatNumber(planTotals.carbs)} g` },
            { label: "Total fat", value: `${formatNumber(planTotals.fat)} g` },
          ].map((row) => (
            <div key={row.label} className="rounded-lg bg-gray-50 p-4">
              <p className="text-xs text-gray-500">{row.label}</p>
              <p className="mt-1 text-lg font-semibold text-gray-900">{row.value}</p>
            </div>
          ))}
        </div>
        {days.length > 0 && (
          <p className="mt-3 text-sm text-gray-500">
            Average per day:{" "}
            {formatNumber(planTotals.calories / days.length)} kcal
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading} disabled={days.length === 0}>
          {submitLabel}
        </Button>
        {days.length === 0 && (
          <span className="text-sm text-gray-500">
            Add at least one day to save.
          </span>
        )}
      </div>
    </form>
  );
}
