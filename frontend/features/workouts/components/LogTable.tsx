"use client";

import { Badge } from "@/components/ui";
import type { WorkoutLog } from "@/types/workout";
import { formatDate } from "./helpers";

interface LogTableProps {
  logs: WorkoutLog[];
  loading?: boolean;
}

export function LogTable({ logs, loading = false }: LogTableProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-500">
        Loading logs…
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
        <p className="text-sm text-gray-500">No workout logs yet.</p>
        <p className="mt-1 text-sm text-gray-400">
          Log a set to start tracking progress.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-6 py-3 font-medium">Date</th>
            <th className="px-6 py-3 font-medium">Exercise</th>
            <th className="px-6 py-3 font-medium">Set</th>
            <th className="px-6 py-3 font-medium">Reps</th>
            <th className="px-6 py-3 font-medium">Weight</th>
            <th className="px-6 py-3 font-medium">Rest</th>
            <th className="px-6 py-3 font-medium">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {logs.map((log) => (
            <tr key={log.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-gray-600">{formatDate(log.date_completed)}</td>
              <td className="px-6 py-4 font-medium text-gray-900">{log.exercise_name}</td>
              <td className="px-6 py-4">
                <Badge variant="default">Set {log.set_number}</Badge>
              </td>
              <td className="px-6 py-4 text-gray-700">
                {log.actual_reps != null ? `${log.actual_reps} reps` : "—"}
              </td>
              <td className="px-6 py-4 text-gray-700">
                {log.actual_weight != null ? `${log.actual_weight} kg` : "—"}
              </td>
              <td className="px-6 py-4 text-gray-700">
                {log.actual_rest_seconds != null ? `${log.actual_rest_seconds}s` : "—"}
              </td>
              <td className="px-6 py-4 text-gray-500">{log.notes || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
