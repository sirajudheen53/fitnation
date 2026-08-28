"use client";

import { create } from "zustand";
import type { AnalyticsFilters, DateRangePreset } from "@/types/analytics";

/**
 * UI state for the analytics dashboard filters (FBOS-030).
 *
 * Server data is managed by React Query; this store only holds the transient
 * filter selections that drive the query keys.
 */
interface AnalyticsFilterState {
  preset: DateRangePreset;
  dateFrom: string;
  dateTo: string;
  branch: string; // "" means "all branches"
  setPreset: (preset: DateRangePreset) => void;
  setDateFrom: (date: string) => void;
  setDateTo: (date: string) => void;
  setBranch: (branch: string) => void;
  reset: () => void;
}

const DEFAULT_STATE = {
  preset: "month" as DateRangePreset,
  dateFrom: "",
  dateTo: "",
  branch: "",
};

export const useAnalyticsFilters = create<AnalyticsFilterState>((set) => ({
  ...DEFAULT_STATE,
  setPreset: (preset) => set({ preset }),
  setDateFrom: (dateFrom) => set({ dateFrom }),
  setDateTo: (dateTo) => set({ dateTo }),
  setBranch: (branch) => set({ branch }),
  reset: () => set({ ...DEFAULT_STATE }),
}));

/**
 * Derive the concrete `AnalyticsFilters` payload from the current store state.
 * Presets map to concrete date ranges; "custom" uses the raw date inputs.
 */
export function resolveAnalyticsFilters(
  state: Pick<AnalyticsFilterState, "preset" | "dateFrom" | "dateTo" | "branch">,
): AnalyticsFilters {
  const filters: AnalyticsFilters = {};

  if (state.branch) {
    filters.branch = state.branch;
  }

  if (state.preset === "custom") {
    if (state.dateFrom) filters.date_from = state.dateFrom;
    if (state.dateTo) filters.date_to = state.dateTo;
    return filters;
  }

  const now = new Date();
  const to = new Date(now);
  const from = new Date(now);

  switch (state.preset) {
    case "today":
      from.setHours(0, 0, 0, 0);
      break;
    case "week":
      from.setDate(now.getDate() - 7);
      break;
    case "month":
      from.setMonth(now.getMonth() - 1);
      break;
    default:
      break;
  }

  filters.date_from = toISODate(from);
  filters.date_to = toISODate(to);
  return filters;
}

function toISODate(date: Date): string {
  return date.toISOString().split("T")[0];
}
