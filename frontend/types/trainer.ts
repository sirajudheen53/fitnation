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

/**
 * POST/PATCH /trainer-schedules/ — the backend keeps exactly one row per
 * (trainer, day_of_week), so a "slot" is the availability window for a day.
 */
export interface TrainerScheduleSlotPayload {
  trainer: number;
  day_of_week: DayOfWeek;
  /** "HH:MM" 24-hour. */
  start_time: string;
  end_time: string;
  is_available: boolean;
}

/** Payload minus trainer — forms/hooks bind the trainer contextually. */
export type ScheduleSlotInput = Omit<TrainerScheduleSlotPayload, "trainer">;

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
  /** Issue #81: the assigned member was deleted (name shows "Deleted user"). */
  customer_is_deleted?: boolean;
  branch_name: string | null;
}

export interface BranchAssignmentCreatePayload {
  trainer: number;
  customer: number;
  branch?: number | null;
}

/** GET /customers/customers/{id}/pt-remaining/ — derived PT pack state. */
export interface PtRemaining {
  customer_id: number;
  membership_id: number | null;
  plan_name: string | null;
  membership_status: "active" | "expired" | "none";
  end_date: string | null;
  total: number | null;
  redeemed: number;
  remaining: number | null;
  unlimited: boolean;
  can_book: boolean;
  reason: string;
}

/** Lifecycle status of a PT session (trainers-app engine). */
export type SessionStatus = "booked" | "completed" | "cancelled" | "no_show";

/** A scheduled personal-training session (/trainer-sessions/). */
export interface TrainerSession {
  id: number;
  trainer: number;
  customer: number;
  branch: number | null;
  /** ISO datetime — the slot start. */
  scheduled_at: string;
  duration_minutes: number;
  status: SessionStatus;
  notes: string;
  trainer_email: string;
  customer_name: string;
  /** Issue #81: the booked member was deleted (name shows "Deleted user"). */
  customer_is_deleted?: boolean;
  branch_name: string | null;
  created_at: string;
  updated_at: string;
}

/** POST /trainer-sessions/ — booking goes through the entitlement + overlap gates. */
export interface SessionBookingPayload {
  trainer: number;
  customer: number;
  branch?: number | null;
  /** ISO datetime (tz-aware) — the slot start. */
  scheduled_at: string;
  duration_minutes?: number;
  notes?: string;
}

/** Machine-readable booking-conflict reasons from the 409 body. */
export const SESSION_CONFLICT_REASONS = [
  "no_active_pt_membership",
  "pt_membership_expired",
  "session_pack_exhausted",
  "trainer_slot_conflict",
] as const;
