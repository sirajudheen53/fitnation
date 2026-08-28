"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert, Spinner } from "@/components/ui";
import { RevenueChart } from "@/features/analytics/components/RevenueChart";
import { AttendanceHeatmapChart } from "@/features/analytics/components/AttendanceHeatmapChart";
import { MembershipFunnelChart } from "@/features/analytics/components/MembershipFunnelChart";
import { TopCustomersTable } from "@/features/analytics/components/TopCustomersTable";
import { AnalyticsFilterBar } from "@/features/analytics/components/AnalyticsFilterBar";
import {
  useAnalyticsFilters,
  resolveAnalyticsFilters,
} from "@/features/analytics/store/analyticsFilters";
import {
  useRevenueReport,
  useAttendanceHeatmap,
  useMembershipFunnel,
  useTopCustomers,
} from "@/features/analytics/hooks/useAnalytics";
import { buildAnalyticsCSV, downloadCSV } from "@/features/analytics/lib/csvExport";
import { fetchBranches, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Branch } from "@/types/branch";

export default function AnalyticsPage() {
  const router = useRouter();
  const [token] = useState<string | null>(() => getToken());
  const [userRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchesError, setBranchesError] = useState<string | null>(null);

  const {
    preset,
    dateFrom,
    dateTo,
    branch,
    setPreset,
    setDateFrom,
    setDateTo,
    setBranch,
  } = useAnalyticsFilters();

  // Role gate: gym_owner / manager (and platform_admin via "*") only.
  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/analytics")) {
      router.replace("/unauthorized");
      return;
    }
    if (userRole === null) return; // still resolving
    if (!token) {
      router.replace("/login?next=/analytics");
    }
  }, [userRole, token, router]);

  // Load branches for the filter dropdown.
  useEffect(() => {
    if (!token) return;
    fetchBranches(token)
      .then((res) => setBranches(Array.isArray(res) ? res : []))
      .catch((err) => setBranchesError(errorMessage(err)));
  }, [token]);

  const filters = useMemo(
    () => resolveAnalyticsFilters({ preset, dateFrom, dateTo, branch }),
    [preset, dateFrom, dateTo, branch],
  );

  const revenue = useRevenueReport(token ?? "", filters);
  const attendance = useAttendanceHeatmap(token ?? "", filters);
  const funnel = useMembershipFunnel(token ?? "", filters);
  const topCustomers = useTopCustomers(token ?? "", filters);

  const loading =
    revenue.isLoading ||
    attendance.isLoading ||
    funnel.isLoading ||
    topCustomers.isLoading;

  const error =
    revenue.error ||
    attendance.error ||
    funnel.error ||
    topCustomers.error;

  const handleExport = () => {
    const csv = buildAnalyticsCSV(
      revenue.data ?? [],
      attendance.data ?? [],
      funnel.data ?? [],
      topCustomers.data ?? [],
    );
    downloadCSV("analytics.csv", csv);
  };

  return (
    <DashboardLayout title="Analytics">
      {error && <Alert variant="error">{errorMessage(error)}</Alert>}
      {branchesError && <Alert variant="warning">{branchesError}</Alert>}

      <AnalyticsFilterBar
        preset={preset}
        dateFrom={dateFrom}
        dateTo={dateTo}
        branch={branch}
        branches={branches}
        onPresetChange={setPreset}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onBranchChange={setBranch}
        onExport={handleExport}
      />

      {loading ? (
        <div className="mt-8 flex items-center justify-center gap-2 text-gray-500">
          <Spinner />
          <span>Loading analytics…</span>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <RevenueChart data={revenue.data ?? []} periodLabel="Revenue" />
          <AttendanceHeatmapChart data={attendance.data ?? []} />
          <MembershipFunnelChart data={funnel.data ?? []} />
          <TopCustomersTable data={topCustomers.data ?? []} />
        </div>
      )}
    </DashboardLayout>
  );
}
