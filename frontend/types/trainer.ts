/**
 * Trainer type definitions — live backend contract (issues #53–#55).
 *
 * Management CRUD lives at /users/trainers/ (users app). The trainers app
 * adds the branch-scoped assignment engine (/trainer-assignments/), weekly
 * availability (/trainer-schedules/) and PT sessions (/trainer-sessions/).
 */

/** Certification entries are free-form JSON on the backend; prefer strings. */
export type TrainerCertification = string | Record<string, unknown>;

export const DAY_OF_WEEK = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const;

export type DayOfWeek = (typeof DAY_OF_WEEK)[number];

/** Weekly availability row (trainers-app /trainer-schedules/). */
export interface TrainerScheduleSlot {
  id: number;
  trainer: number;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  is_available: boolean;
  created_at: string;
  updated_at: string;
}

/** Trainer profile as returned by /users/trainers/ (and /trainers/). */
export interface Trainer {
  id: number;
  user_id: number | null;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  specialization: string | null;
  bio: string | null;
  is_active: boolean;
  certifications: TrainerCertification[];
  experience_years: number | null;
  rating: string;
  profile_photo: string;
  max_clients: number;
  created_at: string;
  updated_at: string;
}

export interface TrainerListParams {
  is_active?: boolean;
  specialization?: string;
  search?: string;
}

/** POST /users/trainers/ — creates the staff user (role=trainer) + profile. */
export interface TrainerCreatePayload {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  /** Optional; when blank the backend sets an unusable password. */
  password?: string;
  specialization?: string;
  bio?: string;
  certifications?: string[];
  experience_years?: number;
  max_clients?: number;
  profile_photo?: string;
}

/** PATCH /users/trainers/{id}/ — profile fields only (user fields immutable). */
export interface TrainerUpdatePayload {
  specialization?: string;
  bio?: string;
  is_active?: boolean;
  certifications?: string[];
  experience_years?: number;
  max_clients?: number;
  profile_photo?: string;
}

/** Branch-scoped trainer↔customer assignment (/trainer-assignments/). */
export interface BranchTrainerAssignment {
  id: number;
  trainer: number;
  customer: number;
  branch: number | null;
  assigned_at: string;
  unassigned_at: string | null;
  is_active: boolean;
  trainer_email: string;
  customer_name: string;
  branch_name: string | null;
}

export interface BranchAssignmentCreatePayload {
  trainer: number;
  customer: number;
  branch?: number | null;
}
