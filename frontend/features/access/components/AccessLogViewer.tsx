"use client";

import { Card, CardBody, CardHeader, Badge } from "@/components/ui";
import { getCustomerDisplayName } from "@/features/customers/components/CustomerTable";
import type { Customer } from "@/types/customer";
import {
  CREDENTIAL_TYPE_LABELS,
  formatAccessTimestamp,
  getEventTypeMeta,
  type AccessDevice,
  type AccessLog,
} from "@/types/access";

const selectClass =
  "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 sm:w-64";

interface AccessLogViewerProps {
  logs: AccessLog[];
  devices: AccessDevice[];
  customers: Customer[];
  loading?: boolean;
  deviceFilter: string;
  onDeviceFilterChange: (value: string) => void;
}

export function AccessLogViewer({
  logs,
  devices,
  customers,
  loading = false,
  deviceFilter,
  onDeviceFilterChange,
}: AccessLogViewerProps) {
  const deviceName = (id: number) =>
    devices.find((d) => d.id === id)?.name ?? `Device #${id}`;

  const customerName = (id: number | null) => {
    if (id === null) return "Unknown";
    const match = customers.find((c) => c.id === id);
    return match ? getCustomerDisplayName(match) : `Customer #${id}`;
  };

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-base font-semibold text-gray-900">Recent entry / exit events</h3>
        <div>
          <label htmlFor="log-device-filter" className="sr-only">
            Filter by device
          </label>
          <select
            id="log-device-filter"
            aria-label="Filter by device"
            value={deviceFilter}
            onChange={(e) => onDeviceFilterChange(e.target.value)}
            className={selectClass}
            data-testid="log-device-filter"
          >
            <option value="">All devices</option>
            {devices.map((d) => (
              <option key={d.id} value={String(d.id)}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        {loading ? (
          <p className="px-6 py-8 text-center text-sm text-gray-500">Loading access logs…</p>
        ) : logs.length === 0 ? (
          <p
            className="px-6 py-8 text-center text-sm text-gray-500"
            data-testid="access-logs-empty"
          >
            No access events recorded yet. Use “Fetch events” on a device to pull its history.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Timestamp</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Customer</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Device</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Event</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Credential</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Device user ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map((log) => {
                  const meta = getEventTypeMeta(log.event_type);
                  return (
                    <tr key={log.id} className="hover:bg-gray-50" data-testid={`access-log-row-${log.id}`}>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                        {formatAccessTimestamp(log.event_timestamp)}
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {customerName(log.customer)}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{deviceName(log.device)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={meta.variant}>{meta.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {CREDENTIAL_TYPE_LABELS[log.credential_type] ?? log.credential_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">
                        {log.device_user_id}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
