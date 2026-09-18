"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Fingerprint, History, Plus, ScrollText } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { DeviceTable, DeviceTableLoading } from "@/features/access/components/DeviceTable";
import { DeviceFormDialog } from "@/features/access/components/DeviceFormDialog";
import { OverridePanel } from "@/features/access/components/OverridePanel";
import { AccessLogViewer } from "@/features/access/components/AccessLogViewer";
import { Alert, Button, Spinner } from "@/components/ui";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import {
  createAccessOverride,
  createDevice,
  errorMessage,
  fetchAccessLogs,
  fetchAccessOverrides,
  fetchCustomers,
  fetchDeviceEvents,
  fetchDevices,
  fetchBranches,
  syncDevice,
  testDeviceConnection,
  updateDevice,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Customer } from "@/types/customer";
import type { Branch } from "@/types/branch";
import type {
  AccessDevice,
  AccessDeviceFormData,
  AccessLog,
  AccessOverride,
  AccessOverrideFormData,
  DeviceEventsResult,
  DeviceSyncResult,
} from "@/types/access";

type PageTab = "devices" | "overrides" | "logs";

const TABS: { key: PageTab; label: string; icon: typeof Fingerprint }[] = [
  { key: "devices", label: "Devices", icon: Fingerprint },
  { key: "overrides", label: "Overrides", icon: History },
  { key: "logs", label: "Access Logs", icon: ScrollText },
];

export default function DevicesPage() {
  const router = useRouter();
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  const [activeTab, setActiveTab] = useState<PageTab>("devices");

  const [devices, setDevices] = useState<AccessDevice[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [overrides, setOverrides] = useState<AccessOverride[]>([]);
  const [logs, setLogs] = useState<AccessLog[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overridesLoaded, setOverridesLoaded] = useState(false);
  const [overridesLoading, setOverridesLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logDeviceFilter, setLogDeviceFilter] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<AccessDevice | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [overrideError, setOverrideError] = useState<unknown>(null);

  const loadLogs = async (deviceFilter: string) => {
    const token = getToken();
    if (!token) return;
    setLogsLoading(true);
    try {
      const list = await fetchAccessLogs(token, {
        device: deviceFilter || undefined,
      });
      setLogs(list);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/devices")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/devices");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        // Customers are needed for override + log display names.
        const [devs, brs, custs] = await Promise.all([
          fetchDevices(authToken),
          fetchBranches(authToken).then((res) => (Array.isArray(res) ? res : [])),
          fetchCustomers(authToken).then((res) => res.results ?? []),
        ]);
        setDevices(devs);
        setBranches(brs);
        setCustomers(custs);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  // Lazy-load tab data on first visit; logs refetch when the filter changes.
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;

    if (activeTab === "overrides" && !overridesLoaded && !overridesLoading) {
      setOverridesLoading(true);
      fetchAccessOverrides(authToken)
        .then((list) => setOverrides(list))
        .catch((err) => toast.error(errorMessage(err)))
        .finally(() => {
          setOverridesLoaded(true);
          setOverridesLoading(false);
        });
    }
    if (activeTab === "logs") {
      loadLogs(logDeviceFilter);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const openAdd = () => {
    setEditingDevice(null);
    setSaveError(null);
    setDialogOpen(true);
  };

  const openEdit = (device: AccessDevice) => {
    setEditingDevice(device);
    setSaveError(null);
    setDialogOpen(true);
  };

  const handleDeviceSubmit = async (data: AccessDeviceFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (editingDevice) {
        const updated = await updateDevice(editingDevice.id, data, token);
        setDevices((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
        toast.success("Device updated");
      } else {
        const created = await createDevice(data, token);
        setDevices((prev) => [created, ...prev]);
        toast.success("Device added");
      }
      setDialogOpen(false);
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = (device: AccessDevice) => {
    const token = getToken();
    if (!token) return Promise.reject(new Error("Not authenticated"));
    return testDeviceConnection(device.id, token);
  };

  const handleSync = async (device: AccessDevice): Promise<DeviceSyncResult> => {
    const token = getToken();
    if (!token) return { synced: false, detail: "Not signed in." };
    try {
      const result = await syncDevice(device.id, token);
      if (result.synced) {
        toast.success(`${device.name}: ${result.detail}`);
        // Refresh to pick up new last_sync_at / last_seen_at stamps.
        fetchDevices(token)
          .then(setDevices)
          .catch(() => undefined);
      } else {
        toast.error(`${device.name}: ${result.detail}`);
      }
      return result;
    } catch (err) {
      const detail = errorMessage(err);
      toast.error(detail);
      return { synced: false, detail };
    }
  };

  const handleFetchEvents = async (device: AccessDevice): Promise<DeviceEventsResult> => {
    const token = getToken();
    if (!token) return { fetched: false, recorded: 0, detail: "Not signed in." };
    try {
      const result = await fetchDeviceEvents(device.id, token);
      if (result.fetched) {
        toast.success(`${device.name}: ${result.detail}`);
        if (activeTab === "logs") loadLogs(logDeviceFilter);
      } else {
        toast.error(`${device.name}: ${result.detail}`);
      }
      return result;
    } catch (err) {
      const detail = errorMessage(err);
      toast.error(detail);
      return { fetched: false, recorded: 0, detail };
    }
  };

  const handleOverrideSubmit = async (data: AccessOverrideFormData) => {
    const token = getToken();
    if (!token) return;
    setOverrideSaving(true);
    setOverrideError(null);
    try {
      const created = await createAccessOverride(data, token);
      setOverrides((prev) => [created, ...prev]);
      setOverridesLoaded(true);
      toast.success(created.allow_access ? "Access granted" : "Access denied");
    } catch (err) {
      setOverrideError(err);
      toast.error(errorMessage(err));
    } finally {
      setOverrideSaving(false);
    }
  };

  const handleLogFilterChange = (value: string) => {
    setLogDeviceFilter(value);
    loadLogs(value);
  };

  return (
    <DashboardLayout
      title="Access Devices"
      actions={
        activeTab === "devices" ? (
          <Button size="sm" onClick={openAdd} data-testid="add-device-btn">
            <Plus className="h-4 w-4" /> Add device
          </Button>
        ) : null
      }
    >
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-1 overflow-x-auto" aria-label="Access control tabs">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  "flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium transition-colors",
                  isActive
                    ? "border-brand-600 text-brand-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
                )}
                aria-current={isActive ? "page" : undefined}
                data-testid={`devices-tab-${tab.key}`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {loading && <DeviceTableLoading />}

      {!loading && !error && activeTab === "devices" && (
        <DeviceTable
          devices={devices}
          branches={branches}
          onTest={handleTest}
          onSync={handleSync}
          onFetchEvents={handleFetchEvents}
          onEdit={openEdit}
        />
      )}

      {!loading && !error && activeTab === "overrides" && (
        overridesLoading ? (
          <div className="flex h-48 items-center justify-center">
            <Spinner />
          </div>
        ) : (
          <OverridePanel
            overrides={overrides}
            customers={customers}
            devices={devices}
            saving={overrideSaving}
            error={overrideError}
            onSubmit={handleOverrideSubmit}
          />
        )
      )}

      {!loading && !error && activeTab === "logs" && (
        <AccessLogViewer
          logs={logs}
          devices={devices}
          customers={customers}
          loading={logsLoading}
          deviceFilter={logDeviceFilter}
          onDeviceFilterChange={handleLogFilterChange}
        />
      )}

      <DeviceFormDialog
        open={dialogOpen}
        device={editingDevice}
        branches={branches}
        saving={saving}
        error={saveError}
        onSubmit={handleDeviceSubmit}
        onClose={() => setDialogOpen(false)}
      />
    </DashboardLayout>
  );
}
