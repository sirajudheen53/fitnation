"use client";

import { X } from "lucide-react";
import { Badge } from "@/components/ui";
import type { NotificationLog } from "@/types/notification";
import {
  getNotificationStatusMeta,
  getNotificationTypeLabel,
} from "@/types/notification";
import { formatLogTimestamp } from "./NotificationLogsTable";

interface LogDetailModalProps {
  log: NotificationLog | null;
  onClose: () => void;
}

export function LogDetailModal({ log, onClose }: LogDetailModalProps) {
  if (!log) return null;
  const meta = getNotificationStatusMeta(log.status);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Notification log detail"
    >
      <div
        className="w-full max-w-lg rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">Notification detail</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">
                {log.customer_name || "No customer"}
              </p>
              <p className="text-xs text-gray-500">{getNotificationTypeLabel(log.notification_type)}</p>
            </div>
            <Badge variant={meta.variant}>{meta.label}</Badge>
          </div>

          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">Message</p>
            <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
              {log.content || "—"}
            </p>
          </div>

          {log.error_message && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-red-500">
                Error
              </p>
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{log.error_message}</p>
            </div>
          )}

          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Wati message ID</dt>
              <dd className="text-gray-900">{log.wati_message_id || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Timestamp</dt>
              <dd className="text-gray-900">{formatLogTimestamp(log.created_at)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
