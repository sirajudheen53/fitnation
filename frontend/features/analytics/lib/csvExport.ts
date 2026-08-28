import type {
  RevenueReport,
  AttendanceHeatmap,
  MembershipFunnel,
  TopCustomer,
} from "@/types/analytics";

/**
 * CSV export helpers for the analytics dashboard (FBOS-030).
 *
 * These build CSV strings client-side and trigger a browser download. They are
 * pure functions so they can be unit-tested without a DOM.
 */

function escapeCell(value: string | number): string {
  const str = String(value);
  // Quote cells containing commas, quotes, or newlines.
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function toCSV(rows: (string | number)[][]): string {
  return rows.map((row) => row.map(escapeCell).join(",")).join("\n");
}

/** Trigger a browser download of the given CSV content. */
export function downloadCSV(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function revenueToCSV(data: RevenueReport[]): string {
  return toCSV([
    ["period", "amount"],
    ...data.map((d) => [d.period, d.amount]),
  ]);
}

export function attendanceToCSV(data: AttendanceHeatmap[]): string {
  return toCSV([
    ["date", "count"],
    ...data.map((d) => [d.date, d.count]),
  ]);
}

export function funnelToCSV(data: MembershipFunnel[]): string {
  return toCSV([
    ["stage", "count"],
    ...data.map((d) => [d.stage, d.count]),
  ]);
}

export function topCustomersToCSV(data: TopCustomer[]): string {
  return toCSV([
    ["customer_id", "customer_name", "total_spent"],
    ...data.map((d) => [d.customer_id, d.customer_name ?? "", d.total_spent]),
  ]);
}

/**
 * Combine all datasets into a single multi-section CSV export. Sections are
 * separated by a blank line and a header row.
 */
export function buildAnalyticsCSV(
  revenue: RevenueReport[],
  attendance: AttendanceHeatmap[],
  funnel: MembershipFunnel[],
  topCustomers: TopCustomer[],
): string {
  const sections: string[] = [];

  sections.push("Revenue Report");
  sections.push(revenueToCSV(revenue));

  sections.push("");
  sections.push("Attendance Heatmap");
  sections.push(attendanceToCSV(attendance));

  sections.push("");
  sections.push("Membership Funnel");
  sections.push(funnelToCSV(funnel));

  sections.push("");
  sections.push("Top Customers");
  sections.push(topCustomersToCSV(topCustomers));

  return sections.join("\n");
}
