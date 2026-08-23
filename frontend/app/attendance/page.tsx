"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AttendanceTable } from "@/features/attendance/components/AttendanceTable";
import { AttendanceStats } from "@/features/attendance/components/AttendanceStats";
import { PeakHoursChart } from "@/features/attendance/components/PeakHoursChart";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchAttendance, fetchAttendanceStats, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { AttendanceRecord } from "@/types/attendance";

export default function AttendancePage() {
  const router = useRouter();
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [stats, setStats] = useState<{
    stats: {
      today_count: number;
      peak_hour: string | null;
      peak_hour_count: number;
      weekly_check_ins: number;
      avg_daily_check_ins: number;
      most_frequent_dropout_hour: string | null;
    };
    summary: { labels: string[]; check_ins: number[] };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
      router.replace("/login?next=/attendance");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [recordRes, statsRes] = await Promise.all([
          fetchAttendance(authToken),
          fetchAttendanceStats(authToken),
        ]);
        setRecords(recordRes.results);
        setStats(statsRes);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const canCheckIn = userRole ? canAccessRoute(userRole, "/attendance/check-in") : false;

  return (
    <DashboardLayout
      title="Attendance"
      actions={
        canCheckIn ? (
          <Link href="/attendance/check-in">
            <Button size="sm">
              <Plus className="h-4 w-4" /> Check in
            </Button>
          </Link>
        ) : null
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && stats && (
        <div className="space-y-6">
          <AttendanceStats stats={stats.stats} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <PeakHoursChart summary={stats.summary} />
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-gray-200 bg-white p-5">
                  <p className="text-sm text-gray-500">Weekly check-ins</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {stats.stats.weekly_check_ins}
                  </p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-5">
                  <p className="text-sm text-gray-500">Avg daily</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {stats.stats.avg_daily_check_ins}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">Recent check-ins</h2>
            <AttendanceTable records={records.slice(0, 10)} />
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
