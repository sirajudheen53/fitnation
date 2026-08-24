/**
 * Diet Plan management type definitions — FBOS-013.
 */

export type DietGoal = "bulk" | "cut" | "maintain";

export type MealType =
  | "breakfast"
  | "morning_snack"
  | "lunch"
  | "evening_snack"
  | "dinner";

export type FoodGroup =
  | "grains"
  | "protein"
  | "vegetable"
  | "fruit"
  | "dairy"
  | "fat"
  | "snack"
  | "beverage";

export interface FoodItem {
  id: number;
  name: string;
  serving_size: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  glycemic_index: number | null;
  food_group: FoodGroup;
  is_veg: boolean;
  created_at: string;
}

export interface FoodItemFormData {
  name: string;
  serving_size: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  glycemic_index?: number | null;
  food_group: FoodGroup;
  is_veg: boolean;
}

export interface DietMeal {
  id: number;
  diet_day: number;
  meal_type: MealType;
  food_item: number;
  food_item_name: string;
  quantity: number;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

export interface DietMealFormData {
  meal_type: MealType;
  food_item: number;
  quantity: number;
}

export interface DietDay {
  id: number;
  diet_plan: number;
  day_number: number;
  total_calories: number;
  notes: string | null;
  meals: DietMeal[];
}

export interface DietDayFormData {
  day_number: number;
  notes?: string;
  meals: DietMealFormData[];
}

export interface DietPlan {
  id: number;
  name: string;
  description: string;
  goal: DietGoal;
  daily_calories: number;
  protein_ratio: number;
  carb_ratio: number;
  fat_ratio: number;
  duration_days: number;
  is_template: boolean;
  created_at: string;
  updated_at: string;
  days: DietDay[];
}

export interface DietPlanFormData {
  name: string;
  description?: string;
  goal: DietGoal;
  daily_calories: number;
  protein_ratio: number;
  carb_ratio: number;
  fat_ratio: number;
  duration_days: number;
  is_template: boolean;
  days: DietDayFormData[];
}

export interface DietAssignment {
  id: number;
  customer: number;
  diet_plan: number;
  diet_plan_name: string;
  customer_name: string;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  assigned_by: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DietAssignmentFormData {
  customer: number;
  diet_plan: number;
  start_date: string;
  end_date?: string;
  notes?: string;
}

export interface FoodItemListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FoodItem[];
}

export interface DietPlanListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: DietPlan[];
}

export interface DietAssignmentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: DietAssignment[];
}

export interface NutritionBreakdown {
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
  protein_calories: number;
  carb_calories: number;
  fat_calories: number;
  protein_grams_per_day: number;
  carb_grams_per_day: number;
  fat_grams_per_day: number;
  protein_percent: number;
  carb_percent: number;
  fat_percent: number;
}
