"use client";

import { Badge } from "@/components/ui";
import type { NotificationLog, NotificationType } from "@/types/notification";
import {
  getNotificationStatusMeta,
  getNotificationTypeLabel,
} from "@/types/notification";

/** Format an ISO timestamp to a readable local date-time. */
export function formatLogTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const NOTIFICATION_TYPE_OPTIONS: NotificationType[] = [
  "check_in",
  "membership_expiry",
  "workout_assigned",
  "payment_received",
];

interface NotificationLogsTableProps {
  logs: NotificationLog[];
  onRowClick: (log: NotificationLog) => void;
}

export function NotificationLogsTable({ logs, onRowClick }: NotificationLogsTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Customer</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Type</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Timestamp</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {logs.map((log) => {
            const meta = getNotificationStatusMeta(log.status);
            return (
              <tr
                key={log.id}
                onClick={() => onRowClick(log)}
                className="cursor-pointer hover:bg-gray-50"
              >
                <td className="px-4 py-3 font-medium text-gray-900">
                  {log.customer_name || "—"}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {getNotificationTypeLabel(log.notification_type)}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={meta.variant}>{meta.label}</Badge>
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {formatLogTimestamp(log.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
