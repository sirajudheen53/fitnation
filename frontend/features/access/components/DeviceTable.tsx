"use client";

import { Fragment, useState } from "react";
import {
  Pencil,
  PlugZap,
  RefreshCw,
  DownloadCloud,
  Building2,
} from "lucide-react";
import { Alert, Badge, Button, Spinner } from "@/components/ui";
import type { Branch } from "@/types/branch";
import {
  formatAccessTimestamp,
  getDeviceStatus,
  VENDOR_LABELS,
  type AccessDevice,
  type DeviceEventsResult,
  type DeviceSyncResult,
  type DeviceTestResult,
} from "@/types/access";

type RowAction = "test" | "sync" | "fetch";

interface DeviceTableProps {
  devices: AccessDevice[];
  branches: Branch[];
  /** Run the connection test; the resolved result is shown inline. */
  onTest: (device: AccessDevice) => Promise<DeviceTestResult>;
  onSync: (device: AccessDevice) => Promise<DeviceSyncResult>;
  onFetchEvents: (device: AccessDevice) => Promise<DeviceEventsResult>;
  onEdit: (device: AccessDevice) => void;
}

/** Group devices by branch, preserving the branch list order. */
export function groupDevicesByBranch(
  devices: AccessDevice[],
  branches: Branch[],
): { branchId: number; branchName: string; devices: AccessDevice[] }[] {
  const groups = new Map<number, AccessDevice[]>();
  for (const device of devices) {
    const list = groups.get(device.branch) ?? [];
    list.push(device);
    groups.set(device.branch, list);
  }
  const ordered = branches
    .filter((b) => groups.has(b.id))
    .map((b) => ({
      branchId: b.id,
      branchName: b.name,
      devices: groups.get(b.id) ?? [],
    }));
  // Devices attached to a branch missing from the list (e.g. deleted).
  for (const [branchId, list] of groups) {
    if (!branches.some((b) => b.id === branchId)) {
      ordered.push({
        branchId,
        branchName: `Branch #${branchId}`,
        devices: list,
      });
    }
  }
  return ordered;
}

export function DeviceTable({
  devices,
  branches,
  onTest,
  onSync,
  onFetchEvents,
  onEdit,
}: DeviceTableProps) {
  const [busy, setBusy] = useState<Record<number, RowAction | undefined>>({});
  const [testResults, setTestResults] = useState<Record<number, DeviceTestResult>>({});

  const run = async (
    device: AccessDevice,
    action: RowAction,
    fn: () => Promise<unknown>,
  ) => {
    setBusy((prev) => ({ ...prev, [device.id]: action }));
    try {
      await fn();
    } finally {
      setBusy((prev) => ({ ...prev, [device.id]: undefined }));
    }
  };

  const handleTest = (device: AccessDevice) =>
    run(device, "test", async () => {
      const result = await onTest(device);
      setTestResults((prev) => ({ ...prev, [device.id]: result }));
    });

  const groups = groupDevicesByBranch(devices, branches);

  if (groups.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
        <p className="text-sm text-gray-500">
          No devices registered yet. Add your first biometric device to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {groups.map((group) => (
        <section key={group.branchId} data-testid={`device-branch-group-${group.branchId}`}>
          <div className="mb-2 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-gray-400" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">
              {group.branchName}
            </h3>
            <Badge variant="default">{group.devices.length}</Badge>
          </div>
          <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Device</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Vendor</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Model</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Serial</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Last sync</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Last seen</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {group.devices.map((device) => {
                  const status = getDeviceStatus(device);
                  const rowBusy = busy[device.id];
                  const testResult = testResults[device.id];
                  return (
                    <Fragment key={device.id}>
                      <tr className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">
                          {device.name}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="info" data-testid={`device-vendor-${device.id}`}>
                            {VENDOR_LABELS[device.vendor] ?? device.vendor}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{device.model || "—"}</td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-600">
                          {device.serial_number}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={status.variant}
                            data-testid={`device-status-${device.id}`}
                          >
                            {status.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {formatAccessTimestamp(device.last_sync_at)}
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {formatAccessTimestamp(device.last_seen_at)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              loading={rowBusy === "test"}
                              disabled={rowBusy !== undefined}
                              onClick={() => handleTest(device)}
                              aria-label={`Test connection ${device.name}`}
                              data-testid={`device-test-btn-${device.id}`}
                            >
                              <PlugZap className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              loading={rowBusy === "sync"}
                              disabled={rowBusy !== undefined}
                              onClick={() => run(device, "sync", () => onSync(device))}
                              aria-label={`Sync now ${device.name}`}
                              data-testid={`device-sync-btn-${device.id}`}
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              loading={rowBusy === "fetch"}
                              disabled={rowBusy !== undefined}
                              onClick={() =>
                                run(device, "fetch", () => onFetchEvents(device))
                              }
                              aria-label={`Fetch events ${device.name}`}
                              data-testid={`device-fetch-btn-${device.id}`}
                            >
                              <DownloadCloud className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onEdit(device)}
                              aria-label={`Edit ${device.name}`}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                      {testResult && (
                        <tr>
                          <td colSpan={8} className="bg-gray-50/70 px-4 py-3">
                            <Alert
                              variant={testResult.online ? "success" : "error"}
                              data-testid={`device-test-result-${device.id}`}
                            >
                              {testResult.detail}
                            </Alert>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

/** Full-width loading state for the devices page. */
export function DeviceTableLoading() {
  return (
    <div className="flex h-48 items-center justify-center rounded-xl border border-gray-200 bg-white">
      <Spinner />
    </div>
  );
}
