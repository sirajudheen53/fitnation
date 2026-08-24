"use client";

import { Badge } from "@/components/ui";
import type { WorkoutAssignment } from "@/types/workout";
import { formatDate } from "./helpers";

interface AssignmentTableProps {
  assignments: WorkoutAssignment[];
  loading?: boolean;
}

export function AssignmentTable({ assignments, loading = false }: AssignmentTableProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-500">
        Loading assignments…
      </div>
    );
  }

  if (assignments.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
        <p className="text-sm text-gray-500">No workout assignments yet.</p>
        <p className="mt-1 text-sm text-gray-400">
          Assign a workout plan to a customer to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-6 py-3 font-medium">Customer</th>
            <th className="px-6 py-3 font-medium">Plan</th>
            <th className="px-6 py-3 font-medium">Start</th>
            <th className="px-6 py-3 font-medium">End</th>
            <th className="px-6 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {assignments.map((a) => (
            <tr key={a.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 font-medium text-gray-900">{a.customer_name}</td>
              <td className="px-6 py-4 text-gray-700">{a.workout_plan_name}</td>
              <td className="px-6 py-4 text-gray-600">{formatDate(a.start_date)}</td>
              <td className="px-6 py-4 text-gray-600">{formatDate(a.end_date)}</td>
              <td className="px-6 py-4">
                {a.is_active ? (
                  <Badge variant="success">Active</Badge>
                ) : (
                  <Badge variant="danger">Inactive</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
