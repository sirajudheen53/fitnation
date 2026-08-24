/**
 * Exercise library type definitions — FBOS-011.
 */

export type ExerciseDifficulty = "beginner" | "intermediate" | "advanced";

export interface ExerciseCategory {
  id: number;
  name: string;
  description: string;
  slug: string;
  exercise_count: number;
  created_at: string;
  updated_at: string;
}

export interface Exercise {
  id: number;
  name: string;
  description: string;
  category: number;
  category_name: string;
  muscle_groups: string[];
  equipment_needed: string[];
  difficulty: ExerciseDifficulty;
  instructions: string[];
  media_url: string | null;
  tips: string;
  contraindications: string;
  created_at: string;
  updated_at: string;
}

export interface ExerciseFormData {
  name: string;
  description: string;
  category: number;
  muscle_groups: string[];
  equipment_needed: string[];
  difficulty: ExerciseDifficulty;
  instructions: string[];
  media_url?: string;
  tips?: string;
  contraindications?: string;
}

export interface ExerciseListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Exercise[];
}

export interface ExerciseCategoryListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ExerciseCategory[];
}

export interface ExerciseFilters {
  category?: string;
  difficulty?: string;
  muscle_group?: string;
  equipment_needed?: string;
  search?: string;
}
