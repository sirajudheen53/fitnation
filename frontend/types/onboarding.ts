/**
 * New Member Onboarding wizard types — FBOS-011 + onboarding-design §3.4.
 *
 * Mirrors `backend/apps/onboarding/serializers.py` (request) and
 * `apps/onboarding/services.py::_finalize_response` (response) exactly.
 * NOTE: the membership block keys the plan as `plan` (not `plan_id`) —
 * per the backend serializer, deviating from the earlier task brief.
 */

import type { Gender } from "./customer";
import type { AccessCredentialType, DeviceSyncResult } from "./access";

/* ── Request payloads ──────────────────────────────────────────── */

export type OnboardingPaymentMethod =
  | "cash"
  | "card"
  | "upi"
  | "bank_transfer"
  | "other"
  | "razorpay";

export interface OnboardingCustomerPayload {
  phone: string;
  name: string;
  email?: string;
  date_of_birth?: string;
  gender?: Gender;
  branch: number;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  notes?: string;
}

export interface OnboardingMembershipPayload {
  /** Plan primary key — the backend field is `plan`, not `plan_id`. */
  plan: number;
  start_date?: string;
  end_date?: string;
}

export interface OnboardingPaymentPayload {
  method: OnboardingPaymentMethod;
  amount?: number;
  notes?: string;
}

export interface OnboardingBiometricPayload {
  device: number;
  credential_type?: AccessCredentialType;
  device_user_id: string;
}

/** The single POST /onboarding/member/ body. */
export interface OnboardingMemberPayload {
  customer: OnboardingCustomerPayload;
  membership: OnboardingMembershipPayload;
  /** Omit entirely for ₹0 trials (backend skips the payment row). */
  payment?: OnboardingPaymentPayload;
  biometrics?: OnboardingBiometricPayload[];
  send_welcome?: boolean;
  send_app_invite?: boolean;
}

/** Razorpay phase-2 callback body (POST …/verify-payment/). */
export interface OnboardingVerifyPaymentPayload {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

/* ── Response blocks ───────────────────────────────────────────── */

/**
 * App-invite outcome. Statuses come from
 * `apps/notifications/services/invite_service.py`: sent / skipped / failed /
 * not_applicable / already_sent. (The task brief said `not_configured`;
 * the backend uses `not_applicable` + `reason` — coded to the backend.)
 */
export type AppInviteStatus =
  | "sent"
  | "skipped"
  | "failed"
  | "not_applicable"
  | "already_sent";

export interface AppInviteBlock {
  status: AppInviteStatus;
  /** flag_off | plan_excludes_app | wati_not_configured | daily_limit_reached | disabled | … */
  reason: string | null;
  channel: "whatsapp" | "sms" | null;
  sent_at: string | null;
  resend_allowed_after: string | null;
}

export interface OnboardingCustomerResult {
  id: number;
  name: string;
  phone: string;
  email: string | null;
  branch: number | null;
  is_active: boolean;
}

export interface OnboardingMembershipResult {
  id: number;
  plan: number;
  plan_name: string;
  start_date: string;
  end_date: string;
  status: string;
}

export interface OnboardingPaymentResult {
  id: number;
  method: string;
  amount: string;
  status: string;
  paid_at: string | null;
}

export interface OnboardingBiometricResult {
  credential_id: number;
  device_id: number;
  device_name: string;
  sync: DeviceSyncResult | null;
}

export interface DoorAccessRow {
  device_id: number;
  allowed: boolean;
  source: string;
  reason: string;
}

export interface OnboardingNotificationRow {
  type: string;
  status: string;
}

/** Entitlement preview (FBOS-011 §5.1a) — what the member gets on the app. */
export interface EntitlementPreview {
  status: "active" | "grace" | "expired" | "none";
  read_only: boolean;
  plan_name: string | null;
  end_date: string | null;
  grace_end_date: string | null;
  gym?: { uuid: string; name: string };
}

/** Razorpay checkout params handed back on the two-phase path. */
export interface RazorpayCheckoutParams {
  key: string;
  order_id: string | null;
  amount: number | null;
  currency: string;
}

/** The composite POST /onboarding/member/ response. */
export interface OnboardingResult {
  onboarding_id: string;
  status: "completed" | "pending_payment";
  returning_member?: boolean;
  customer: OnboardingCustomerResult;
  membership: OnboardingMembershipResult | null;
  payment: OnboardingPaymentResult | null;
  invoice_number: string | null;
  biometrics: OnboardingBiometricResult[];
  door_access: DoorAccessRow[];
  notifications: OnboardingNotificationRow[];
  app_invite: AppInviteBlock;
  entitlement_preview?: EntitlementPreview;
  razorpay_checkout?: RazorpayCheckoutParams;
}
