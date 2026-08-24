/**
 * Shared nutrition helpers for the diet module — FBOS-013.
 */

import type { FoodItem } from "@/types/diet";

export const MEAL_TYPE_LABELS: Record<string, string> = {
  breakfast: "Breakfast",
  morning_snack: "Morning Snack",
  lunch: "Lunch",
  evening_snack: "Evening Snack",
  dinner: "Dinner",
};

export const GOAL_LABELS: Record<string, string> = {
  bulk: "Bulk",
  cut: "Cut",
  maintain: "Maintain",
};

export const FOOD_GROUP_LABELS: Record<string, string> = {
  grains: "Grains",
  protein: "Protein",
  vegetable: "Vegetable",
  fruit: "Fruit",
  dairy: "Dairy",
  fat: "Fat",
  snack: "Snack",
  beverage: "Beverage",
};

/** Compute a meal's nutrition from a food item and quantity multiplier. */
export function mealNutrition(
  food: Pick<FoodItem, "calories" | "protein" | "carbs" | "fat">,
  quantity: number,
): { calories: number; protein: number; carbs: number; fat: number } {
  return {
    calories: round1(food.calories * quantity),
    protein: round1(food.protein * quantity),
    carbs: round1(food.carbs * quantity),
    fat: round1(food.fat * quantity),
  };
}

/** Sum nutrition across a list of meals (either persisted or draft). */
export function sumNutrition(
  meals: Array<{
    calories?: number;
    protein?: number;
    carbs?: number;
    fat?: number;
  }>,
): { calories: number; protein: number; carbs: number; fat: number } {
  return meals.reduce<{ calories: number; protein: number; carbs: number; fat: number }>(
    (acc, m) => {
      acc.calories += m.calories ?? 0;
      acc.protein += m.protein ?? 0;
      acc.carbs += m.carbs ?? 0;
      acc.fat += m.fat ?? 0;
      return acc;
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );
}

/** Round a number to one decimal place. */
export function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/** Format a number for display, dropping trailing zeros. */
export function formatNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(round1(value));
}
