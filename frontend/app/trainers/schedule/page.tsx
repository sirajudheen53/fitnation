"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert, Spinner } from "@/components/ui";
import { fetchSchedule, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import {
  formatDayName,
  formatTime,
} from "@/features/trainers/components/scheduleHelpers";
import type { ScheduleSlot } from "@/types/trainer";

export default function SchedulePage() {
  const router = useRouter();
  const [slots, setSlots] = useState<ScheduleSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/trainers")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers/schedule");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchSchedule(authToken);
        setSlots(res.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  return (
    <DashboardLayout title="Trainer schedule">
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && slots.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No schedule slots yet.</p>
        </div>
      )}
      {!loading && slots.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-6 py-3 font-medium">Day</th>
                <th className="px-6 py-3 font-medium">Trainer</th>
                <th className="px-6 py-3 font-medium">Start</th>
                <th className="px-6 py-3 font-medium">End</th>
                <th className="px-6 py-3 font-medium">Session</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {slots.map((slot) => (
                <tr key={slot.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">
                    {formatDayName(slot.day_of_week)}
                  </td>
                  <td className="px-6 py-4 text-gray-700">{slot.trainer_name}</td>
                  <td className="px-6 py-4 text-gray-600">{formatTime(slot.start_time)}</td>
                  <td className="px-6 py-4 text-gray-600">{formatTime(slot.end_time)}</td>
                  <td className="px-6 py-4 text-gray-700">{slot.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DashboardLayout>
  );
}
