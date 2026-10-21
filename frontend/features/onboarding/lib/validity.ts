/**
 * Membership validity helpers for the onboarding wizard (onboarding-design
 * §2 step 2). Pure date math so the "valid 20 Sep → 19 Oct" summary and the
 * editable end-date override stay unit-testable.
 */

/** Format a Date as a `YYYY-MM-DD` string (local time, no TZ drift). */
export function toISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Today as `YYYY-MM-DD`. */
export function todayISO(): string {
  return toISODate(new Date());
}

/** Add `days` to an ISO date string, returning an ISO date string. */
export function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  date.setDate(date.getDate() + days);
  return toISODate(date);
}

/**
 * Default membership window: start (default today) → start + duration.
 * Mirrors the backend `_resolve_dates` (start + plan.duration_days).
 */
export function computeDefaultWindow(
  durationDays: number,
  startOverride?: string,
): { start_date: string; end_date: string } {
  const start = startOverride && startOverride !== "" ? startOverride : todayISO();
  return { start_date: start, end_date: addDays(start, durationDays) };
}

/** Number of whole days between two ISO dates (b - a). */
export function daysBetween(aISO: string, bISO: string): number {
  const a = new Date(`${aISO}T00:00:00`).getTime();
  const b = new Date(`${bISO}T00:00:00`).getTime();
  if (Number.isNaN(a) || Number.isNaN(b)) return 0;
  return Math.round((b - a) / 86_400_000);
}

/** "20 Sep 2026" for an ISO date; the raw string when unparseable. */
export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
