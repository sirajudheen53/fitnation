"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchRevenueReport,
  fetchAttendanceHeatmap,
  fetchMembershipFunnel,
  fetchTopCustomers,
} from "@/lib/api";
import type { AnalyticsFilters } from "@/types/analytics";

/**
 * React Query hooks for the analytics dashboard (FBOS-030).
 *
 * Each hook fetches one analytics dataset, keyed by the active filters so that
 * changing the date range or branch automatically refetches.
 */

export function useRevenueReport(token: string, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "revenue", filters],
    queryFn: () => fetchRevenueReport(token, filters),
    enabled: !!token,
  });
}

export function useAttendanceHeatmap(token: string, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "attendance-heatmap", filters],
    queryFn: () => fetchAttendanceHeatmap(token, filters),
    enabled: !!token,
  });
}

export function useMembershipFunnel(token: string, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "membership-funnel", filters],
    queryFn: () => fetchMembershipFunnel(token, filters),
    enabled: !!token,
  });
}

export function useTopCustomers(token: string, filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ["analytics", "top-customers", filters],
    queryFn: () => fetchTopCustomers(token, filters),
    enabled: !!token,
  });
}
