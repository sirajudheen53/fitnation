/**
 * App-access presentation helpers for the customer detail panel (FBOS-011
 * F3 / ADR-003). Pure functions so the state derivation and invite copy are
 * unit-testable — the SERVER remains the authority; this is display-only.
 */

import type { AppAccessState, AppInviteStatusSummary, Customer } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";

/** The platform grace window (config.settings.base.APP_ACCESS_GRACE_DAYS). */
export const APP_ACCESS_GRACE_DAYS = 7;

export interface AppAccessDisplay {
  status: "active" | "grace" | "expired" | "none" | "unknown";
  label: string;
  /** Badge variant for the status chip. */
  variant: "success" | "warning" | "danger" | "default";
  planName: string | null;
  endDate: string | null;
  /** "Read-only until <date>" when in grace. */
  graceEndDate: string | null;
}

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  date.setDate(date.getDate() + days);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Derive the display state for the panel.
 *
 * Prefers the backend's `app_access` entitlement block when present; falls
 * back to deriving from the member's latest non-cancelled membership + its
 * plan (mirrors `get_app_entitlement`'s date rules, minus the tenant flag
 * which the ERP cannot see — "unknown" when nothing is derivable).
 */
export function deriveAppAccessDisplay(
  customer: Customer,
  memberships: Membership[] | null,
  plans: MembershipPlan[],
  today: string,
): AppAccessDisplay {
  const server = customer.app_access;
  if (server) {
    const labels: Record<AppAccessState["status"], string> = {
      active: "Entitled",
      grace: "Read-only grace",
      expired: "Not entitled",
      none: "Not entitled",
    };
    return {
      status: server.status,
      label: labels[server.status],
      variant:
        server.status === "active"
          ? "success"
          : server.status === "grace"
            ? "warning"
            : "danger",
      planName: server.plan_name,
      endDate: server.end_date,
      graceEndDate: server.grace_end_date,
    };
  }

  // Fallback: latest non-cancelled membership (same max-end_date rule).
  const latest = (memberships ?? [])
    .filter((m) => m.status !== "cancelled")
    .sort((a, b) => b.end_date.localeCompare(a.end_date))[0];
  if (!latest) {
    return {
      status: "unknown",
      label: "No membership",
      variant: "default",
      planName: null,
      endDate: null,
      graceEndDate: null,
    };
  }
  const plan = plans.find((p) => p.id === latest.plan_id) ?? null;
  if (plan && plan.includes_app_access === false) {
    return {
      status: "none",
      label: "Plan excludes app",
      variant: "danger",
      planName: plan.name,
      endDate: latest.end_date,
      graceEndDate: null,
    };
  }
  const active = today <= latest.end_date;
  const graceEnd = addDays(latest.end_date, APP_ACCESS_GRACE_DAYS);
  if (active) {
    return {
      status: "active",
      label: "Entitled",
      variant: "success",
      planName: latest.plan_name,
      endDate: latest.end_date,
      graceEndDate: null,
    };
  }
  if (today <= graceEnd) {
    return {
      status: "grace",
      label: "Read-only grace",
      variant: "warning",
      planName: latest.plan_name,
      endDate: latest.end_date,
      graceEndDate: graceEnd,
    };
  }
  return {
    status: "expired",
    label: "Expired",
    variant: "danger",
    planName: latest.plan_name,
    endDate: latest.end_date,
    graceEndDate: null,
  };
}

export interface InviteDisplay {
  /** Short chip label for the last invite attempt. */
  label: string;
  /** The machine outcome this chip describes (null = never invited). */
  status: string | null;
  variant: "success" | "warning" | "danger" | "default";
  /** CTA text; null when the backend contract makes a send pointless. */
  actionLabel: "Send app invite" | "Resend invite" | "Retry invite" | null;
  /** Whether the CTA must force (`resend: true`) past the 24 h dedupe. */
  force: boolean;
  detail: string | null;
}

/**
 * Human copy for the backend's `not_applicable` reasons (#102). The invite
 * service returns these before any send is attempted, so resending cannot
 * change the outcome — the chip must say WHY and drop the CTA.
 */
const NOT_APPLICABLE_COPY: Record<string, { label: string; detail: string }> = {
  flag_off: {
    label: "App invites not enabled for this gym",
    detail: "App access is not enabled for this gym yet — the invite cannot go out until it is.",
  },
  plan_excludes_app: {
    label: "Plan does not include the app",
    detail: "This member's plan does not include app access.",
  },
};

function notApplicableCopy(reason: string | null): { label: string; detail: string } {
  return (
    NOT_APPLICABLE_COPY[reason ?? ""] ?? {
      label: "Invite not applicable to this member",
      detail: "The server declined the invite for this member's current plan or gym settings.",
    }
  );
}

/** Toast copy for the outcome of one send attempt (#102). */
export interface InviteOutcomeToast {
  kind: "success" | "warning" | "error";
  message: string;
}

/** Map an `app_invite` response block onto the send toast (never raw codes). */
export function inviteOutcomeToast(invite: AppInviteStatusSummary): InviteOutcomeToast {
  switch (invite.status) {
    case "sent":
      return {
        kind: "success",
        message: `Invite sent via ${invite.channel === "sms" ? "SMS" : "WhatsApp"}`,
      };
    case "already_sent":
      return { kind: "success", message: "Invite was already sent recently" };
    case "not_applicable":
      return {
        kind: "warning",
        message: notApplicableCopy(invite.error_message).detail,
      };
    case "skipped":
      return {
        kind: "warning",
        message:
          invite.error_message ?? "Invite not sent — WhatsApp is not configured for this gym yet.",
      };
    case "failed":
      return {
        kind: "error",
        message: invite.error_message ? `Invite failed: ${invite.error_message}` : "Invite failed",
      };
    default:
      return { kind: "warning", message: `Invite outcome was "${invite.status}" — no message went out.` };
  }
}

/** Map `Customer.app_invite_status` onto the panel's chip + CTA. */
export function describeInviteStatus(
  invite: AppInviteStatusSummary | null | undefined,
): InviteDisplay {
  if (!invite) {
    return {
      label: "Never invited",
      status: null,
      variant: "default",
      actionLabel: "Send app invite",
      force: false,
      detail: null,
    };
  }
  const channel = invite.channel === "sms" ? "SMS" : "WhatsApp";
  const sentAt = invite.sent_at
    ? new Date(invite.sent_at).toLocaleString("en-IN")
    : null;
  switch (invite.status) {
    case "sent":
      return {
        label: `Invite sent via ${channel}`,
        status: invite.status,
        variant: "success",
        actionLabel: "Resend invite",
        force: true,
        detail: sentAt ? `Last sent ${sentAt}` : null,
      };
    case "failed":
      return {
        label: "Invite failed",
        status: invite.status,
        variant: "danger",
        actionLabel: "Retry invite",
        force: false,
        detail: invite.error_message ?? null,
      };
    case "skipped":
      return {
        label: "Invite not sent",
        status: invite.status,
        variant: "warning",
        actionLabel: "Send app invite",
        force: false,
        detail: invite.error_message ?? "WhatsApp not configured for this gym yet.",
      };
    case "not_applicable": {
      // #102: the raw machine value ("not_applicable") read like "not
      // available" next to the card's "Entitled" badge. Name the actual
      // blocker and drop the CTA — resending returns the same verdict.
      const copy = notApplicableCopy(invite.error_message);
      return {
        label: copy.label,
        status: invite.status,
        variant: "warning",
        actionLabel: null,
        force: false,
        detail: copy.detail,
      };
    }
    case "already_sent":
      return {
        label: "Invite already sent",
        status: invite.status,
        variant: "success",
        actionLabel: "Resend invite",
        force: true,
        detail: sentAt ? `Last sent ${sentAt}` : null,
      };
    default:
      // Unknown machine status: never surface the bare code as the state —
      // quote it as a system value so the owner knows what to report (#102).
      return {
        label: "Unknown invite state",
        status: invite.status,
        variant: "default",
        actionLabel: "Resend invite",
        force: true,
        detail: sentAt ? `Last invite recorded as "${invite.status}" · ${sentAt}` : `Last invite recorded as "${invite.status}"`,
      };
  }
}
