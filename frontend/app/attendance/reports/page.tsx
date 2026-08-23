"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AttendanceTable } from "@/features/attendance/components/AttendanceTable";
import { Alert, Spinner, Button } from "@/components/ui";
import { fetchAttendance, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { AttendanceRecord } from "@/types/attendance";

export default function AttendanceReportsPage() {
  const router = useRouter();
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");
  const [customerFilter, setCustomerFilter] = useState("");
  const [branchFilter, setBranchFilter] = useState("");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/attendance")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/attendance/reports");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchAttendance(authToken);
        setRecords(res.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const filteredRecords = useMemo(() => {
    const now = new Date();
    return records.filter((r) => {
      const recordDate = new Date(r.date);

      if (period === "daily") {
        const start = new Date(now);
        start.setHours(0, 0, 0, 0);
        if (recordDate < start || recordDate > now) return false;
      } else if (period === "weekly") {
        const weekAgo = new Date(now);
        weekAgo.setDate(now.getDate() - 7);
        if (recordDate < weekAgo) return false;
      } else {
        const monthAgo = new Date(now);
        monthAgo.setMonth(now.getMonth() - 1);
        if (recordDate < monthAgo) return false;
      }

      if (
        customerFilter &&
        !r.person_name.toLowerCase().includes(customerFilter.toLowerCase())
      ) {
        return false;
      }
      if (branchFilter && r.branch_name && !r.branch_name.includes(branchFilter)) {
        return false;
      }
      return true;
    });
  }, [records, period, customerFilter, branchFilter]);

  const exportCsv = () => {
    const header = ["Name", "Type", "Branch", "Check-in", "Check-out", "Status"];
    const rows = filteredRecords.map((r) => [
      r.person_name,
      r.person_type,
      r.branch_name ?? "",
      r.check_in_time ?? "",
      r.check_out_time ?? "",
      r.status,
    ]);
    const csv = [header, ...rows]
      .map((row) => row.map((c) => `"${c}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "attendance-report.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <DashboardLayout
      title="Attendance reports"
      actions={
        <Button size="sm" variant="outline" onClick={exportCsv} disabled={filteredRecords.length === 0}>
          Export CSV
        </Button>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-3 rounded-xl border border-gray-200 bg-white p-4 md:grid-cols-4">
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value as "daily" | "weekly" | "monthly")}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
            <input
              type="text"
              placeholder="Filter by customer"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <input
              type="text"
              placeholder="Filter by branch"
              value={branchFilter}
              onChange={(e) => setBranchFilter(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <div className="flex items-center text-sm text-gray-600">
              {filteredRecords.length} record{filteredRecords.length === 1 ? "" : "s"}
            </div>
          </div>

          <AttendanceTable
            records={filteredRecords}
            emptyMessage="No attendance records match the selected filters."
          />
        </div>
      )}
    </DashboardLayout>
  );
}
