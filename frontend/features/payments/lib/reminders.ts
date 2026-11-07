/**
 * Payment-reminder outcome presentation for the pending-payments surfaces
 * (dashboard card + payments queue). Pure functions so the toast copy for
 * gate/skip/cap outcomes is unit-testable — the SERVER remains the authority
 * on why a reminder did not go out; this is display-only (#106).
 */

import { errorMessage } from "@/lib/api";
import type { SendPaymentLinkResponse } from "@/types/payment";

/** Toast copy for the outcome of one reminder send. */
export interface PaymentReminderToast {
  kind: "success" | "info" | "error";
  message: string;
}

/** Semantic channel values read like log lines — display them properly. */
const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "email",
};

/**
 * Map a send-link outcome onto the row toast (never raw machine codes).
 * `sent` and `already_sent` are the good paths; everything else — a skipped
 * channel/template gate, an unreachable member — surfaces the backend's
 * human reason verbatim, so the desk always sees WHY nothing went out (#106).
 */
export function paymentReminderToast(
  outcome: SendPaymentLinkResponse,
  customerName: string,
): PaymentReminderToast {
  if (outcome.status === "sent") {
    const channel = CHANNEL_LABELS[outcome.channel ?? ""] ?? outcome.channel;
    return {
      kind: "success",
      message: `Payment link sent to ${customerName} over ${channel}`,
    };
  }
  if (outcome.status === "already_sent") {
    return {
      kind: "info",
      message: `A payment link was sent to ${customerName} recently — try again later.`,
    };
  }
  return {
    kind: "error",
    message: outcome.reason || `Could not send a payment link to ${customerName}`,
  };
}

/**
 * Human text for a reminder send the API rejected outright — the 429 daily
 * cap, the 400 not-pending / gate detail — through the #96 errorMessage
 * chain, so the response `detail` surfaces verbatim instead of a silent
 * no-op (#106).
 */
export const paymentReminderErrorText = errorMessage;
