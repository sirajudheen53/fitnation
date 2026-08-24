/**
 * Workout Builder helper functions — FBOS-012.
 */

import type { DayOfWeek, WorkoutDifficulty, WorkoutGoal } from "@/types/workout";

export const GOAL_LABELS: Record<WorkoutGoal, string> = {
  strength: "Strength",
  hypertrophy: "Hypertrophy",
  endurance: "Endurance",
  weight_loss: "Weight Loss",
  general_fitness: "General Fitness",
};

export const GOAL_OPTIONS: { value: WorkoutGoal; label: string }[] = [
  { value: "strength", label: "Strength" },
  { value: "hypertrophy", label: "Hypertrophy" },
  { value: "endurance", label: "Endurance" },
  { value: "weight_loss", label: "Weight Loss" },
  { value: "general_fitness", label: "General Fitness" },
];

export const DIFFICULTY_LABELS: Record<WorkoutDifficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export const DIFFICULTY_OPTIONS: { value: WorkoutDifficulty; label: string }[] = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

export const DAY_OF_WEEK_LABELS: Record<DayOfWeek, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};

export const DAY_OF_WEEK_OPTIONS: { value: DayOfWeek; label: string }[] = [
  { value: "monday", label: "Monday" },
  { value: "tuesday", label: "Tuesday" },
  { value: "wednesday", label: "Wednesday" },
  { value: "thursday", label: "Thursday" },
  { value: "friday", label: "Friday" },
  { value: "saturday", label: "Saturday" },
  { value: "sunday", label: "Sunday" },
];

export function goalBadgeVariant(
  goal: WorkoutGoal,
): "default" | "info" | "success" | "warning" | "danger" {
  switch (goal) {
    case "strength":
      return "danger";
    case "hypertrophy":
      return "info";
    case "endurance":
      return "success";
    case "weight_loss":
      return "warning";
    case "general_fitness":
      return "default";
    default:
      return "default";
  }
}

export function difficultyBadgeVariant(
  difficulty: WorkoutDifficulty,
): "default" | "info" | "success" | "warning" | "danger" {
  switch (difficulty) {
    case "beginner":
      return "success";
    case "intermediate":
      return "warning";
    case "advanced":
      return "danger";
    default:
      return "default";
  }
}

/** Human-readable label for a workout day (focus, day-of-week, or number). */
export function dayLabel(day: {
  focus?: string;
  day_of_week?: DayOfWeek | "";
  day_number?: number | null;
}): string {
  if (day.focus) return day.focus;
  if (day.day_of_week) return DAY_OF_WEEK_LABELS[day.day_of_week] ?? day.day_of_week;
  if (day.day_number) return `Day ${day.day_number}`;
  return "Day";
}

/** Format a date string for display. */
export function formatDate(date: string | null | undefined): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString();
}
