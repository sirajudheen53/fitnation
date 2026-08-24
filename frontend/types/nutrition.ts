/**
 * AI Nutrition type definitions — FBOS-019.
 */

export interface MealItem {
  id: number;
  name: string;
  quantity: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

export interface Meal {
  id: number;
  name: string;
  time: string | null;
  items: MealItem[];
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
}

export interface MealPlanDay {
  id: number;
  day_number: number;
  day_label: string;
  meals: Meal[];
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
}

export interface MealPlan {
  id: number;
  name: string;
  description: string;
  target_calories: number;
  cuisine: string | null;
  created_at: string;
  updated_at: string;
  days: MealPlanDay[];
}

export interface MealPlanListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: MealPlan[];
}

export interface GenerateMealPlanRequest {
  target_calories: number;
  cuisine?: string;
}

export interface MacroSummary {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

export interface ShoppingListItem {
  id: number;
  name: string;
  quantity: string;
  category: string | null;
  checked: boolean;
}

export interface ShoppingList {
  id: number;
  name: string;
  meal_plan: number | null;
  items: ShoppingListItem[];
  created_at: string;
  updated_at: string;
}

export interface ShoppingListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ShoppingList[];
}
