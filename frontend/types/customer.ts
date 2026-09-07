/**
 * Customer type definitions.
 */

export type Gender = "male" | "female" | "other" | "prefer_not_to_say";

export type FitnessGoal =
  | "weight_loss"
  | "muscle_gain"
  | "endurance"
  | "strength"
  | "flexibility"
  | "general_fitness"
  | "rehabilitation"
  | "sports_performance";

export interface Customer {
  id: number;
  email: string;
  /** Fields returned by GET /customers/customers/ (backend contract). */
  user: number;
  name: string;
  branch: number | null;
  status: string;
  notes: string;
  address_street: string;
  address_city: string;
  address_state: string;
  address_postal_code: string;
  phone: string | null;
  gender: Gender | null;
  date_of_birth: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  is_active: boolean;
  profile_photo: string | null;
  created_at: string;
  updated_at: string;
  /**
   * Legacy fields kept optional for existing call sites. The backend does
   * NOT return them (health data lives on the separate health-profile
   * endpoint); display code must prefer `name`.
   */
  first_name?: string;
  last_name?: string;
  branch_id?: number | null;
  height_cm?: number | string | null;
  weight_kg?: number | string | null;
  bmi?: number | string | null;
  fitness_goal?: FitnessGoal | null;
  injuries?: string | null;
  medical_info?: string | null;
}

export interface CustomerFormData {
  /**
   * Upload/replace photo (File), explicitly remove an existing photo (null),
   * or leave unchanged (undefined). Serialised as multipart when a File is
   * present, otherwise as JSON (null included so the backend can clear it).
   */
  profile_photo?: File | null;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  gender?: Gender;
  date_of_birth?: string;
  branch_id?: number;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  is_active: boolean;
}

export interface HealthProfileFormData {
  height_cm?: number;
  weight_kg?: number;
  bmi?: number;
  fitness_goal?: FitnessGoal;
  injuries?: string;
  medical_info?: string;
}

export interface CustomerListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Customer[];
}