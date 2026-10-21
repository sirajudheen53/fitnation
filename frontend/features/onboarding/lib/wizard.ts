/**
 * Onboarding wizard state, payload building and invite-status presentation
 * (FBOS-011 + onboarding-design). Kept as pure functions so the payload the
 * wizard sends and the success-screen chip states are unit-testable.
 */

import type { Customer, Gender } from "@/types/customer";
import type { AccessCredentialType } from "@/types/access";
import type { MembershipPlan } from "@/types/membership";
import type {
  AppInviteBlock,
  OnboardingMemberPayload,
  OnboardingPaymentMethod,
} from "@/types/onboarding";

/** Payment methods offered at the desk (Razorpay = two-phase online). */
export const DESK_PAYMENT_METHODS: { value: OnboardingPaymentMethod; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "upi", label: "UPI" },
  { value: "card", label: "Card" },
  { value: "razorpay", label: "Razorpay (online)" },
];

export const GENDER_OPTIONS: { value: Gender; label: string }[] = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
];

export const GENDER_LABELS: Record<string, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

/** All wizard state in one place — the wizard page is the single owner. */
export interface OnboardingFormState {
  // Step 1 — Who
  phone: string;
  name: string;
  dateOfBirth: string;
  gender: Gender;
  branchId: number | null;
  email: string;
  emergencyContactName: string;
  emergencyContactPhone: string;
  notes: string;
  /** Non-null when the phone lookup matched an existing member. */
  returningMember: Customer | null;
  // Step 2 — Plan & payment
  planId: number | null;
  startDate: string;
  /** True once the user hand-edits the end date (stops auto-recalc). */
  endDateOverridden: boolean;
  endDate: string;
  paymentMethod: OnboardingPaymentMethod | null;
  amount: string;
  paymentNotes: string;
  // Step 3 — Biometric
  deviceId: number | null;
  deviceUserId: string;
  credentialType: AccessCredentialType;
}

export function initialFormState(branchId: number | null): OnboardingFormState {
  return {
    phone: "",
    name: "",
    dateOfBirth: "",
    gender: "prefer_not_to_say",
    branchId,
    email: "",
    emergencyContactName: "",
    emergencyContactPhone: "",
    notes: "",
    returningMember: null,
    planId: null,
    startDate: "",
    endDateOverridden: false,
    endDate: "",
    paymentMethod: null,
    amount: "",
    paymentNotes: "",
    deviceId: null,
    deviceUserId: "",
    credentialType: "fingerprint",
  };
}

/** A ₹0 trial hides the whole payment block (onboarding-design §2). */
export function isFreeTrial(plan: MembershipPlan | null): boolean {
  return plan !== null && plan.plan_type === "trial" && Number(plan.price) === 0;
}

/**
 * Build the POST /onboarding/member/ body from the wizard state.
 *
 * Empty optional fields are omitted (the backend defaults them); the
 * payment block is omitted entirely for free trials; `biometrics` is `[]`
 * when the desk skipped enrollment — both explicitly supported by the
 * backend contract.
 */
export function buildOnboardingPayload(
  state: OnboardingFormState,
  plan: MembershipPlan,
): OnboardingMemberPayload {
  const customer: OnboardingMemberPayload["customer"] = {
    phone: state.phone.trim(),
    name: state.name.trim(),
    branch: state.branchId as number,
  };
  if (state.email.trim() !== "") customer.email = state.email.trim();
  if (state.dateOfBirth !== "") customer.date_of_birth = state.dateOfBirth;
  if (state.gender !== "prefer_not_to_say") customer.gender = state.gender;
  if (state.emergencyContactName.trim() !== "") {
    customer.emergency_contact_name = state.emergencyContactName.trim();
  }
  if (state.emergencyContactPhone.trim() !== "") {
    customer.emergency_contact_phone = state.emergencyContactPhone.trim();
  }
  if (state.notes.trim() !== "") customer.notes = state.notes.trim();

  const membership: OnboardingMemberPayload["membership"] = {
    plan: plan.id,
    start_date: state.startDate,
    end_date: state.endDate,
  };

  const freeTrial = isFreeTrial(plan);
  const payment = freeTrial || state.paymentMethod === null
    ? undefined
    : {
        method: state.paymentMethod,
        amount: Number(state.amount) || 0,
        notes: state.paymentNotes.trim() || undefined,
      };

  const biometrics =
    state.deviceId !== null && state.deviceUserId.trim() !== ""
      ? [
          {
            device: state.deviceId,
            credential_type: state.credentialType,
            device_user_id: state.deviceUserId.trim(),
          },
        ]
      : [];

  return { customer, membership, payment, biometrics };
}

export interface InviteChip {
  variant: "success" | "warning" | "danger";
  /** Short headline, e.g. "WhatsApp invite sent". */
  label: string;
  /** Longer explanation (reason copy) shown under the label. */
  description: string | null;
  /** True when a Resend action can plausibly help (failed invites). */
  resend: boolean;
}

const REASON_COPY: Record<string, string> = {
  wati_not_configured:
    "WhatsApp is not configured for this gym yet — set it up under Settings → WhatsApp.",
  plan_excludes_app: "This plan does not include app access.",
  flag_off: "App access is not enabled for this gym yet.",
  daily_limit_reached: "Daily invite limit reached — try again tomorrow.",
  disabled: "Invite skipped (disabled for this onboarding).",
  pending_payment: "Invite sends after the online payment completes.",
};

/** Map an `app_invite` response block onto the success-screen chip. */
export function describeAppInvite(invite: AppInviteBlock | null | undefined): InviteChip {
  if (!invite) {
    return { variant: "warning", label: "Invite status unknown", description: null, resend: false };
  }
  switch (invite.status) {
    case "sent":
      return {
        variant: "success",
        label: invite.channel === "sms" ? "SMS invite sent" : "WhatsApp invite sent",
        description: null,
        resend: false,
      };
    case "already_sent":
      return {
        variant: "success",
        label: "Invite already sent",
        description: "The member received an invite recently — no duplicate was sent.",
        resend: false,
      };
    case "failed":
      return {
        variant: "danger",
        label: "Invite failed",
        description: invite.reason ? REASON_COPY[invite.reason] ?? invite.reason : null,
        resend: true,
      };
    case "not_applicable":
      return {
        variant: "warning",
        label: "App not included",
        description: invite.reason ? REASON_COPY[invite.reason] ?? invite.reason : null,
        resend: false,
      };
    case "skipped":
    default:
      return {
        variant: "warning",
        label: "Invite not sent",
        description: invite.reason ? REASON_COPY[invite.reason] ?? invite.reason : null,
        resend: false,
      };
  }
}

/** Human label for a payment method value (response or segmented control). */
export function paymentMethodLabel(method: string | null | undefined): string {
  if (!method) return "—";
  const labels: Record<string, string> = {
    cash: "Cash",
    upi: "UPI",
    card: "Card",
    bank_transfer: "Bank transfer",
    other: "Other",
    razorpay: "Razorpay (online)",
    online: "Online (Razorpay)",
  };
  return labels[method] ?? method;
}
