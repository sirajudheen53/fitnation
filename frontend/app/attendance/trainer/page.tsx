"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AttendanceTable } from "@/features/attendance/components/AttendanceTable";
import { Alert, Spinner } from "@/components/ui";
import { fetchAttendance, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { AttendanceRecord } from "@/types/attendance";

export default function TrainerAttendancePage() {
  const router = useRouter();
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<"week" | "month">("week");
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
      router.replace("/login?next=/attendance/trainer");
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

  const trainerRecords = useMemo(() => {
    const now = new Date();
    return records.filter((r) => {
      if (r.person_type !== "trainer") return false;
      const recordDate = new Date(r.date);
      if (period === "week") {
        const weekAgo = new Date(now);
        weekAgo.setDate(now.getDate() - 7);
        if (recordDate < weekAgo) return false;
      } else {
        const monthAgo = new Date(now);
        monthAgo.setMonth(now.getMonth() - 1);
        if (recordDate < monthAgo) return false;
      }
      return true;
    });
  }, [records, period]);

  const presentCount = useMemo(
    () => trainerRecords.filter((r) => r.status !== "absent").length,
    [trainerRecords],
  );
  const absentCount = trainerRecords.length - presentCount;

  return (
    <DashboardLayout title="Trainer attendance">
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <div className="space-y-6">
          <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex gap-6">
              <div>
                <p className="text-sm text-gray-500">On time</p>
                <p className="text-xl font-semibold text-green-600">
                  {trainerRecords.filter((r) => r.status === "present").length}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Late</p>
                <p className="text-xl font-semibold text-amber-600">
                  {trainerRecords.filter((r) => r.status === "late").length}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Absent</p>
                <p className="text-xl font-semibold text-red-600">{absentCount}</p>
              </div>
            </div>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value as "week" | "month")}
              className="block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="week">Last 7 days</option>
              <option value="month">Last 30 days</option>
            </select>
          </div>

          <AttendanceTable
            records={trainerRecords}
            emptyMessage="No trainer attendance records found."
          />
        </div>
      )}
    </DashboardLayout>
  );
}
