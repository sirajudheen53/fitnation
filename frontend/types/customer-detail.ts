/**
 * FBOS-025 — Customer detail sub-resource types.
 * (Fitness goals, body measurements, health profile, progress photos, progress summary.)
 */

/* ── Health profile ───────────────────────────────────────────── */

export type BloodGroup =
  | "A+"
  | "A-"
  | "B+"
  | "B-"
  | "AB+"
  | "AB-"
  | "O+"
  | "O-"
  | "unknown";

export interface HealthProfile {
  id: number;
  customer: number;
  height_cm: string | number | null;
  weight_kg: string | number | null;
  bmi: string | number | null;
  blood_group: BloodGroup;
  injuries: string;
  current_injuries: string[];
  past_injuries: string[];
  medical_info: Record<string, unknown>;
  medical_conditions: string[];
  allergies: string[];
  food_allergies: string[];
  medications: string[];
  dietary_restrictions: string[];
  created_at: string;
  updated_at: string;
}

export interface HealthProfileUpdate {
  height_cm?: number;
  weight_kg?: number;
  blood_group?: BloodGroup;
  injuries?: string;
  current_injuries?: string[];
  past_injuries?: string[];
  medical_conditions?: string[];
  allergies?: string[];
  food_allergies?: string[];
  medications?: string[];
  dietary_restrictions?: string[];
}

/* ── Fitness goals ────────────────────────────────────────────── */

export type FitnessGoalType =
  | "lose_weight"
  | "build_muscle"
  | "endurance"
  | "flexibility"
  | "general_fitness"
  | "sport_specific"
  | "other";

export type FitnessGoalStatus = "active" | "achieved" | "abandoned";

export interface CustomerFitnessGoal {
  id: number;
  customer: number;
  goal_type: FitnessGoalType;
  is_active: boolean;
  status: FitnessGoalStatus;
  target_value: string | number | null;
  target_unit: string;
  target_date: string | null;
  current_value: string | number | null;
  progress_percentage: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface FitnessGoalFormData {
  goal_type: FitnessGoalType;
  target_value?: number;
  target_unit?: string;
  target_date?: string;
  current_value?: number;
  status?: FitnessGoalStatus;
  notes?: string;
}

/* ── Body measurements ────────────────────────────────────────── */

export interface BodyMeasurement {
  id: number;
  customer: number;
  date_logged: string;
  weight_kg: string | number;
  height_cm: string | number | null;
  bmi: string | number | null;
  body_fat_percentage: string | number | null;
  chest_cm: string | number | null;
  waist_cm: string | number | null;
  hips_cm: string | number | null;
  biceps_cm: string | number | null;
  thighs_cm: string | number | null;
  neck_cm: string | number | null;
  arms_cm: string | number | null;
  legs_cm: string | number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface BodyMeasurementFormData {
  weight_kg: number;
  height_cm?: number;
  body_fat_percentage?: number;
  chest_cm?: number;
  waist_cm?: number;
  hips_cm?: number;
  biceps_cm?: number;
  thighs_cm?: number;
  neck_cm?: number;
  arms_cm?: number;
  legs_cm?: number;
  notes?: string;
}

/* ── Progress photos ──────────────────────────────────────────── */

export interface ProgressPhoto {
  id: number;
  customer: number;
  image: string;
  caption: string;
  taken_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProgressPhotoFormData {
  image: string;
  caption?: string;
}

/* ── Progress summary ─────────────────────────────────────────── */

export interface WeightTrendPoint {
  date_logged: string;
  weight_kg: string | number;
}

export interface ProgressSummary {
  customer_id: number;
  customer_name: string;
  health_profile: HealthProfile | null;
  latest_measurement: BodyMeasurement | null;
  weight_trend: WeightTrendPoint[];
  fitness_goals: CustomerFitnessGoal[];
  progress_photo_count: number;
}

/* ── Display helpers ──────────────────────────────────────────── */

export const FITNESS_GOAL_TYPE_LABELS: Record<FitnessGoalType, string> = {
  lose_weight: "Lose Weight",
  build_muscle: "Build Muscle",
  endurance: "Endurance",
  flexibility: "Flexibility",
  general_fitness: "General Fitness",
  sport_specific: "Sport Specific",
  other: "Other",
};

export const BLOOD_GROUP_OPTIONS: BloodGroup[] = [
  "A+",
  "A-",
  "B+",
  "B-",
  "AB+",
  "AB-",
  "O+",
  "O-",
  "unknown",
];

export function getFitnessGoalLabel(type: FitnessGoalType): string {
  return FITNESS_GOAL_TYPE_LABELS[type] ?? type;
}
