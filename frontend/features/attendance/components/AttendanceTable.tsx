"use client";

import { Badge } from "@/components/ui";
import type { AttendanceRecord, AttendanceStatus } from "@/types/attendance";

const STATUS_VARIANTS: Record<AttendanceStatus, "success" | "warning" | "danger" | "info"> = {
  present: "success",
  late: "warning",
  absent: "danger",
  left: "info",
};

export function getAttendanceStatusLabel(status: AttendanceStatus): string {
  const labels: Record<AttendanceStatus, string> = {
    present: "Present",
    late: "Late",
    absent: "Absent",
    left: "Left",
  };
  return labels[status];
}

export function formatTime(time: string | null): string {
  if (!time) return "—";
  const d = new Date(time);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

interface AttendanceTableProps {
  records: AttendanceRecord[];
  loading?: boolean;
  emptyMessage?: string;
}

export function AttendanceTable({
  records,
  loading = false,
  emptyMessage = "No attendance records found.",
}: AttendanceTableProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-500">
        Loading attendance…
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
        <p className="text-sm text-gray-500">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-6 py-3 font-medium">Name</th>
            <th className="px-6 py-3 font-medium">Type</th>
            <th className="px-6 py-3 font-medium">Branch</th>
            <th className="px-6 py-3 font-medium">Check-in</th>
            <th className="px-6 py-3 font-medium">Check-out</th>
            <th className="px-6 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {records.map((record) => (
            <tr key={record.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 font-medium text-gray-900">{record.person_name}</td>
              <td className="px-6 py-4 capitalize text-gray-600">{record.person_type}</td>
              <td className="px-6 py-4 text-gray-600">{record.branch_name ?? "—"}</td>
              <td className="px-6 py-4 text-gray-600">{formatTime(record.check_in_time)}</td>
              <td className="px-6 py-4 text-gray-600">{formatTime(record.check_out_time)}</td>
              <td className="px-6 py-4">
                <Badge variant={STATUS_VARIANTS[record.status]}>
                  {getAttendanceStatusLabel(record.status)}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
