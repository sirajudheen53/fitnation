"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  NotificationLogsTable,
  NOTIFICATION_TYPE_OPTIONS,
} from "@/features/notifications/components/NotificationLogsTable";
import { LogDetailModal } from "@/features/notifications/components/LogDetailModal";
import { Alert, Spinner, Button } from "@/components/ui";
import { fetchNotificationLogs, unwrapNotificationLogs, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { NotificationLog, NotificationStatus, NotificationType } from "@/types/notification";

export default function NotificationLogsPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<NotificationLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLog, setSelectedLog] = useState<NotificationLog | null>(null);

  const [statusFilter, setStatusFilter] = useState<"all" | NotificationStatus>("all");
  const [typeFilter, setTypeFilter] = useState<"all" | NotificationType>("all");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/settings")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/notifications/logs");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchNotificationLogs(authToken, {
          status: statusFilter === "all" ? undefined : statusFilter,
          notification_type: typeFilter === "all" ? undefined : typeFilter,
        });
        setLogs(unwrapNotificationLogs(res));
        setError(null);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole, statusFilter, typeFilter]);

  const emptyState = useMemo(
    () => !loading && logs.length === 0 && !error,
    [loading, logs, error],
  );

  return (
    <DashboardLayout
      title="Notification logs"
      actions={
        <Link href="/notifications/settings">
          <Button size="sm" variant="outline">
            Settings
          </Button>
        </Link>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
          <option value="skipped">Skipped</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          aria-label="Filter by notification type"
        >
          <option value="all">All types</option>
          {NOTIFICATION_TYPE_OPTIONS.map((type) => (
            <option key={type} value={type}>
              {type.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {emptyState && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <Bell className="mx-auto mb-3 h-8 w-8 text-gray-300" />
          <p className="text-sm text-gray-500">No notification logs yet.</p>
        </div>
      )}
      {!loading && logs.length > 0 && (
        <NotificationLogsTable logs={logs} onRowClick={setSelectedLog} />
      )}

      <LogDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
    </DashboardLayout>
  );
}
