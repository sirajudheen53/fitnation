/**
 * Renewal preview helpers — shared by the memberships page and the
 * customer-detail membership card so the confirm dialog always shows the
 * same computed new end date the backend will apply.
 */
import type { Membership, MembershipPlan } from "@/types/membership";

/** ISO (yyyy-mm-dd) date shifted by N days, built from local components so
 * timezone conversion can't move the result across a day boundary. */
export function addDaysISO(dateStr: string, days: number): string | null {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  d.setDate(d.getDate() + days);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

/** Days a renewal adds: the membership plan's duration, else 30
 * (mirrors the backend default when the plan can't be resolved). */
export const RENEWAL_FALLBACK_DAYS = 30;

export function renewalDays(
  membership: Membership,
  plans: MembershipPlan[],
): number {
  const plan = plans.find((p) => p.id === membership.plan_id);
  return plan?.duration_days || RENEWAL_FALLBACK_DAYS;
}

/** Computed new end date (ISO yyyy-mm-dd) for a renewal preview,
 * or null when the current end date isn't a usable date. */
export function renewalNewEndDate(
  membership: Membership,
  plans: MembershipPlan[],
): string | null {
  return addDaysISO(membership.end_date, renewalDays(membership, plans));
}
