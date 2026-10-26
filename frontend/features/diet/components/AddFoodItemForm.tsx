"use client";

import { useState } from "react";
import { Button, Input, Alert } from "@/components/ui";
import type { DishMealType, FoodGroup, FoodItemFormData } from "@/types/diet";

const FOOD_GROUPS: { value: FoodGroup; label: string }[] = [
  { value: "grains", label: "Grains" },
  { value: "protein", label: "Protein" },
  { value: "vegetable", label: "Vegetable" },
  { value: "fruit", label: "Fruit" },
  { value: "dairy", label: "Dairy" },
  { value: "fat", label: "Fat" },
  { value: "snack", label: "Snack" },
  { value: "beverage", label: "Beverage" },
];

const MEAL_SLOTS: { value: DishMealType; label: string }[] = [
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "snack", label: "Snack" },
  { value: "dinner", label: "Dinner" },
];

interface AddFoodItemFormProps {
  submitLabel?: string;
  onSubmit: (data: FoodItemFormData) => void | Promise<void>;
  onCancel?: () => void;
}

/** Client-side create-dish form (ticket #89). Posts to POST /food-items/. */
export function AddFoodItemForm({
  submitLabel = "Add dish",
  onSubmit,
  onCancel,
}: AddFoodItemFormProps) {
  const [name, setName] = useState("");
  const [servingSize, setServingSize] = useState("1 serving");
  const [calories, setCalories] = useState("");
  const [protein, setProtein] = useState("0");
  const [carbs, setCarbs] = useState("0");
  const [fat, setFat] = useState("0");
  const [fiber, setFiber] = useState("0");
  const [foodGroup, setFoodGroup] = useState<FoodGroup>("protein");
  const [mealType, setMealType] = useState<DishMealType | "">("");
  const [isVeg, setIsVeg] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const macroRaw = [calories, protein, carbs, fat, fiber];
    if (!name.trim()) {
      setValidationError("Dish name is required.");
      return;
    }
    if (!servingSize.trim()) {
      setValidationError("Serving size is required.");
      return;
    }
    if (macroRaw.some((raw) => raw.trim() !== "" && Number.isNaN(Number(raw)))) {
      setValidationError("Nutrition values must be numbers.");
      return;
    }
    const macroValues = macroRaw.map((raw) => Number(raw));
    if (macroValues.some((v) => v < 0)) {
      setValidationError("Nutrition values cannot be negative.");
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        serving_size: servingSize.trim(),
        calories: Number(calories),
        protein: Number(protein),
        carbs: Number(carbs),
        fat: Number(fat),
        fiber: Number(fiber),
        food_group: foodGroup,
        meal_type: mealType || null,
        is_dish: true,
        is_veg: isVeg,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4"
      aria-label="Add dish form"
      noValidate
    >
      {validationError && <Alert variant="error">{validationError}</Alert>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input
          label="Dish name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Grilled Paneer Salad"
        />
        <Input
          label="Serving size"
          value={servingSize}
          onChange={(e) => setServingSize(e.target.value)}
          placeholder="e.g. 1 bowl (200g)"
        />
        <Input
          label="Calories (kcal)"
          type="number"
          min="0"
          value={calories}
          onChange={(e) => setCalories(e.target.value)}
        />
        <Input
          label="Protein (g)"
          type="number"
          min="0"
          step="0.1"
          value={protein}
          onChange={(e) => setProtein(e.target.value)}
        />
        <Input
          label="Carbs (g)"
          type="number"
          min="0"
          step="0.1"
          value={carbs}
          onChange={(e) => setCarbs(e.target.value)}
        />
        <Input
          label="Fat (g)"
          type="number"
          min="0"
          step="0.1"
          value={fat}
          onChange={(e) => setFat(e.target.value)}
        />
        <Input
          label="Fiber (g)"
          type="number"
          min="0"
          step="0.1"
          value={fiber}
          onChange={(e) => setFiber(e.target.value)}
        />
        <div className="space-y-1.5">
          <label
            htmlFor="food-group"
            className="block text-sm font-medium text-gray-700"
          >
            Food group
          </label>
          <select
            id="food-group"
            value={foodGroup}
            onChange={(e) => setFoodGroup(e.target.value as FoodGroup)}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {FOOD_GROUPS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor="meal-type"
            className="block text-sm font-medium text-gray-700"
          >
            Meal slot (optional)
          </label>
          <select
            id="meal-type"
            value={mealType}
            onChange={(e) => setMealType(e.target.value as DishMealType | "")}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Any meal</option>
            {MEAL_SLOTS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-6 pt-6">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={isVeg}
              onChange={(e) => setIsVeg(e.target.checked)}
            />
            Vegetarian
          </label>
        </div>
      </div>
      <div className="flex gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving…" : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
