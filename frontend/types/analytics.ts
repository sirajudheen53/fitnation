/**
 * Types for Analytics endpoints — FBOS-030.
 */

export interface RevenueReport {
  period: string; // ISO date string representing the start of the period
  amount: number; // revenue amount in smallest currency unit
}

export interface AttendanceHeatmap {
  date: string; // ISO date
  count: number; // attendance count for that day
}

export interface MembershipFunnel {
  stage: string; // e.g., "prospect", "trial", "active", "cancelled"
  count: number;
}

export interface TopCustomer {
  customer_id: number;
  total_spent: number;
  /** Optional display name — not yet returned by the backend contract. */
  customer_name?: string | null;
}

/** Date-range presets supported by the analytics dashboard filters. */
export type DateRangePreset = "today" | "week" | "month" | "custom";

/** Query parameters accepted by the analytics endpoints. */
export interface AnalyticsFilters {
  date_from?: string;
  date_to?: string;
  branch?: number | string;
}
