/**
 * Exercise library helper functions — FBOS-011.
 */

import type { ExerciseDifficulty } from "@/types/exercise";

export const DIFFICULTY_LABELS: Record<ExerciseDifficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export const DIFFICULTY_OPTIONS: { value: ExerciseDifficulty; label: string }[] = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

export const MUSCLE_GROUP_OPTIONS = [
  "chest",
  "back",
  "shoulders",
  "biceps",
  "triceps",
  "forearms",
  "core",
  "quadriceps",
  "hamstrings",
  "glutes",
  "calves",
  "lats",
  "traps",
  "lower_back",
  "hip_flexors",
  "ankles",
  "hips",
  "spine",
  "legs",
  "arms",
  "rear_delts",
];

export const EQUIPMENT_OPTIONS = [
  "barbell",
  "dumbbells",
  "dumbbell",
  "kettlebell",
  "bench",
  "squat rack",
  "cable machine",
  "rope attachment",
  "pull-up bar",
  "leg press machine",
  "treadmill",
  "stationary bike",
  "rowing machine",
  "elliptical machine",
  "stair climber",
  "jump rope",
  "resistance band",
  "box",
  "platform",
  "punching bag",
  "boxing gloves",
  "broomstick",
  "step",
];

export function formatDifficulty(difficulty: ExerciseDifficulty): string {
  return DIFFICULTY_LABELS[difficulty] ?? difficulty;
}

export function difficultyBadgeVariant(
  difficulty: ExerciseDifficulty,
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

export function formatMuscleGroup(muscleGroup: string): string {
  return muscleGroup
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function formatEquipment(equipment: string): string {
  return equipment
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function isMediaUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return /^https?:\/\//i.test(url);
}

export function isVideoUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return /\.(mp4|webm|ogg|mov)(\?.*)?$/i.test(url) || /youtube\.com|youtu\.be|vimeo\.com/i.test(url);
}

export function isImageUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return /\.(jpe?g|png|gif|webp|bmp|svg)(\?.*)?$/i.test(url);
}
