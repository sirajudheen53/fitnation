/**
 * PT sessions board helpers (issue #55).
 */

/** Local YYYY-MM-DD key for an ISO datetime. */
export function sessionDayKey(iso: string): string {
  const d = new Date(iso);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

/** Monday 00:00 of the week containing `now`. */
export function weekStart(now = new Date()): Date {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekday = (d.getDay() + 6) % 7; // 0 = Monday
  d.setDate(d.getDate() - weekday);
  return d;
}

/** Inclusive range [startIso, endIso) for "today" | "week". */
export function rangeBounds(
  range: "today" | "week",
  now = new Date(),
): { start: Date; end: Date } {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(start);
  if (range === "today") {
    end.setDate(start.getDate() + 1);
  } else {
    const monday = weekStart(now);
    start.setTime(monday.getTime());
    end.setTime(monday.getTime());
    end.setDate(monday.getDate() + 7);
  }
  return { start, end };
}

/** "Today" / "Tomorrow" / "Wed, Oct 22" for a day key within the current week. */
export function dayLabel(dayKey: string, now = new Date()): string {
  const [y, m, d] = dayKey.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffDays = Math.round((date.getTime() - today.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

/** "09:00" clock label for an ISO datetime. */
export function sessionTimeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
