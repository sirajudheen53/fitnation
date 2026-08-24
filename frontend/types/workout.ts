/**
 * Workout Builder type definitions — FBOS-012.
 */

export type WorkoutGoal =
  | "strength"
  | "hypertrophy"
  | "endurance"
  | "weight_loss"
  | "general_fitness";

export type WorkoutDifficulty = "beginner" | "intermediate" | "advanced";

export type DayOfWeek =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export interface WorkoutExercise {
  id: number;
  workout_day: number;
  exercise: number;
  exercise_name: string;
  exercise_details: {
    id: number;
    name: string;
    category_name: string;
    muscle_groups: string[];
    equipment_needed: string[];
    difficulty: WorkoutDifficulty;
  } | null;
  sets: number;
  reps: string;
  rest_seconds: number;
  tempo: string | null;
  rpe: number | null;
  notes: string | null;
  order: number;
  alternate_exercise: number | null;
  alternate_exercise_name: string | null;
}

export interface WorkoutExerciseFormData {
  exercise: number;
  sets: number;
  reps: string;
  rest_seconds: number;
  tempo?: string;
  rpe?: number | null;
  notes?: string;
  order: number;
  alternate_exercise?: number | null;
}

export interface WorkoutDay {
  id: number;
  workout_plan: number;
  day_of_week: DayOfWeek | "";
  day_number: number | null;
  focus: string;
  notes: string | null;
  exercises: WorkoutExercise[];
}

export interface WorkoutDayFormData {
  day_of_week?: DayOfWeek;
  day_number?: number | null;
  focus?: string;
  notes?: string;
  exercises: WorkoutExerciseFormData[];
}

export interface WorkoutPlan {
  id: number;
  name: string;
  description: string;
  goal: WorkoutGoal;
  difficulty: WorkoutDifficulty;
  duration_weeks: number;
  is_template: boolean;
  created_by: number | null;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  days: WorkoutDay[];
}

export interface WorkoutPlanFormData {
  name: string;
  description?: string;
  goal: WorkoutGoal;
  difficulty: WorkoutDifficulty;
  duration_weeks: number;
  is_template: boolean;
  days: WorkoutDayFormData[];
}

export interface WorkoutAssignment {
  id: number;
  customer: number;
  workout_plan: number;
  workout_plan_name: string;
  customer_name: string;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  assigned_by: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkoutAssignmentFormData {
  customer: number;
  workout_plan: number;
  start_date: string;
  end_date?: string;
  notes?: string;
}

export interface WorkoutLog {
  id: number;
  customer: number;
  workout_exercise: number;
  workout_day: number;
  exercise_name: string;
  customer_name: string;
  date_completed: string;
  set_number: number;
  actual_reps: number | null;
  actual_weight: number | null;
  actual_rest_seconds: number | null;
  notes: string | null;
  created_at: string;
}

export interface WorkoutLogFormData {
  customer: number;
  workout_exercise: number;
  workout_day: number;
  date_completed: string;
  set_number: number;
  actual_reps?: number | null;
  actual_weight?: number | null;
  actual_rest_seconds?: number | null;
  notes?: string;
}

export interface WorkoutPlanListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: WorkoutPlan[];
}

export interface WorkoutAssignmentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: WorkoutAssignment[];
}

export interface WorkoutLogListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: WorkoutLog[];
}
