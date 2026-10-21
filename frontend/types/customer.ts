/**
 * Customer type definitions.
 */

import type { PaymentMethod } from "./payment";

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
  /**
   * Optional (msg 2438): phone-only customers carry a NULL email and log in
   * via phone OTP under a synthetic identity; adding a real email later
   * adopts it onto the same account.
   */
  email: string | null;
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
   * FBOS-011 §5.1b: the most recent app-invite notification for the member,
   * or null when never invited. Optional so pre-feature payloads stay typed.
   */
  app_invite_status?: AppInviteStatusSummary | null;
  /**
   * App-access entitlement derived from the member's plan (ADR-003):
   * active / read-only grace / not entitled. OPTIONAL — the backend list
   * serializer does not expose this yet; UI falls back to "unknown" until
   * it lands.
   */
  app_access?: AppAccessState | null;
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

/** Last app_invite NotificationLog summary (CustomerSerializer.app_invite_status). */
export interface AppInviteStatusSummary {
  status: string;
  channel: string | null;
  sent_at: string | null;
  error_message: string | null;
}

/**
 * App-access entitlement for a member (backend `AppEntitlement.as_payload`
 * shape). `status` mirrors `get_app_entitlement`: "active" (full access),
 * "grace" (read-only until grace_end_date), "expired"/"none" (gated out).
 */
export interface AppAccessState {
  status: "active" | "grace" | "expired" | "none";
  read_only: boolean;
  plan_name: string | null;
  end_date: string | null;
  grace_end_date: string | null;
}

/** Admission-fee capture on the customer create form (form-only, never sent
 * to the customer endpoint — the caller turns it into a Payment row). */
export interface AdmissionFeeInput {
  amount: number;
  /** "completed" = paid now with the chosen method, "pending" = collect later. */
  status: "completed" | "pending";
  method: PaymentMethod;
}

export interface CustomerFormData {
  /**
   * Upload/replace photo (File), explicitly remove an existing photo (null),
   * or leave unchanged (undefined). Serialised as multipart when a File is
   * present, otherwise as JSON (null included so the backend can clear it).
   */
  profile_photo?: File | null;
  /** Optional (msg 2438); empty string normalizes to NULL backend-side. */
  email?: string;
  first_name: string;
  last_name?: string;
  phone?: string;
  gender?: Gender;
  date_of_birth?: string;
  branch_id?: number;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  address_street?: string;
  address_city?: string;
  address_state?: string;
  address_postal_code?: string;
  /** Form-only admission-fee capture (create flow); stripped by buildCustomerBody. */
  admission_fee?: AdmissionFeeInput;
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