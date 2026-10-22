"use client";

import { useEffect, useState } from "react";
import { ScanFace, X } from "lucide-react";
import { toast } from "sonner";
import { Alert, Badge, Button, Card, CardBody, CardHeader, Spinner } from "@/components/ui";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { getToken } from "@/lib/auth";
import {
  deactivateBiometricCredential,
  enrollBiometricCredential,
  fetchAccessCredentials,
  fetchCustomerAttendance,
  fetchDevices,
  errorMessage,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { AttendanceRecord } from "@/types/attendance";
import {
  ACCESS_CREDENTIAL_TYPES,
  CREDENTIAL_TYPE_LABELS,
  formatAccessTimestamp,
  type AccessCredential,
  type AccessDevice,
  type EnrollCredentialResult,
} from "@/types/access";

/** How many recent attendance rows the front desk needs on this tab. */
const ATTENDANCE_LIMIT = 10;

const selectClass =
  "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

/** ADMS devices record punches in IST — render this tab's clocks in Asia/Calcutta
 * regardless of where the browser (or the CI runner) sits. */
const ATTENDANCE_TIME_ZONE = "Asia/Calcutta";

/** "2026-10-22" → "22 Oct 2026"; returns the input when unparseable. */
export function formatAttendanceDate(date: string): string {
  const parsed = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: ATTENDANCE_TIME_ZONE,
  });
}

/** ISO timestamp → "9:05 am" (IST); "—" for null/punches that never closed. */
export function formatAttendanceTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString("en-IN", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: ATTENDANCE_TIME_ZONE,
  });
}

/** Newest first, capped for the front-desk view. */
export function recentAttendance(records: AttendanceRecord[]): AttendanceRecord[] {
  return [...records]
    .sort((a, b) => {
      const byDate = b.date.localeCompare(a.date);
      if (byDate !== 0) return byDate;
      return (b.check_in_time ?? "").localeCompare(a.check_in_time ?? "");
    })
    .slice(0, ATTENDANCE_LIMIT);
}

interface BiometricTabProps {
  customer: Customer;
}

export function BiometricTab({ customer }: BiometricTabProps) {
  const [devices, setDevices] = useState<AccessDevice[]>([]);
  const [credentials, setCredentials] = useState<AccessCredential[]>([]);
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  /** Last successful enroll — drives the prominent device-user-id callout. */
  const [enrolled, setEnrolled] = useState<EnrollCredentialResult | null>(null);
  const [enrollDevice, setEnrollDevice] = useState("");
  const [enrollType, setEnrollType] = useState<string>("fingerprint");

  const [confirmTarget, setConfirmTarget] = useState<AccessCredential | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;

    async function load() {
      try {
        const [creds, devs, attendanceRes] = await Promise.all([
          fetchAccessCredentials(authToken, { customer: customer.id }),
          fetchDevices(authToken),
          fetchCustomerAttendance(customer.id, authToken),
        ]);
        setCredentials(creds);
        setDevices(devs);
        setAttendance(attendanceRes.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [customer.id]);

  const deviceName = (id: number) =>
    devices.find((d) => d.id === id)?.name ?? `Device #${id}`;

  const activeDevices = devices.filter((d) => d.is_active);

  const openDialog = () => {
    setEnrollDevice("");
    setEnrollType("fingerprint");
    setSaveError(null);
    setDialogOpen(true);
  };

  const submitEnroll = async () => {
    const device = Number(enrollDevice);
    if (!enrollDevice || Number.isNaN(device)) {
      setSaveError(new Error("Select a device"));
      return;
    }
    const credentialType = enrollType as (typeof ACCESS_CREDENTIAL_TYPES)[number];
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      // No device_user_id sent: the backend allocates/reuses the customer's
      // canonical tenant-wide id and returns it for the device keypad.
      const result = await enrollBiometricCredential(
        { customer: customer.id, device, credential_type: credentialType },
        token,
      );
      setCredentials((prev) => [
        result.credential,
        ...prev.filter((c) => c.id !== result.credential.id),
      ]);
      setEnrolled(result);
      setDialogOpen(false);
      toast.success(`Enrolled on ${deviceName(device)} · ${result.sync.detail ?? "synced"}`);
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const submitDeactivate = async () => {
    if (!confirmTarget) return;
    const token = getToken();
    if (!token) return;
    setDeactivating(true);
    try {
      const updated = await deactivateBiometricCredential(confirmTarget.id, token);
      setCredentials((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(`Deactivated on ${deviceName(updated.device)}`);
      setConfirmTarget(null);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeactivating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && <Alert variant="error">{error}</Alert>}

      {enrolled && (
        <div
          className="rounded-xl border border-brand-200 bg-brand-50 p-5"
          data-testid="enroll-result"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-brand-800">
                Credential enrolled on {deviceName(enrolled.credential.device)} ·{" "}
                {CREDENTIAL_TYPE_LABELS[enrolled.credential.credential_type]}
              </p>
              <p className="mt-3 text-xs uppercase tracking-wide text-brand-700">Device user ID</p>
              <p
                className="mt-1 font-mono text-3xl font-bold text-brand-900"
                data-testid="enrolled-device-user-id"
              >
                {enrolled.credential.device_user_id}
              </p>
              <p className="mt-2 text-sm text-brand-700">
                Type this exact ID on the device during enrollment.
              </p>
            </div>
            <button
              onClick={() => setEnrolled(null)}
              aria-label="Dismiss"
              className="rounded-lg p-1.5 text-brand-500 hover:bg-brand-100 hover:text-brand-700"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <ScanFace className="h-4 w-4 text-gray-400" />
            <div>
              <h3 className="text-base font-semibold text-gray-900">Biometric credentials</h3>
              <p className="mt-0.5 text-sm text-gray-500">
                The device user ID is assigned automatically and shared across all devices.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={openDialog}
            disabled={activeDevices.length === 0}
            data-testid="biometric-enroll-btn"
          >
            Enroll biometric
          </Button>
        </CardHeader>
        <CardBody className="p-0">
          {activeDevices.length === 0 && (
            <p className="border-b border-gray-100 px-6 py-3 text-sm text-amber-700">
              No active devices registered yet — add one under Access Devices before enrolling.
            </p>
          )}
          {credentials.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-gray-500" data-testid="credentials-empty">
              No biometric credentials enrolled for this customer yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Device</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Credential</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Device user ID</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Enrolled</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-500">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {credentials.map((cred) => (
                    <tr key={cred.id} className="hover:bg-gray-50" data-testid={`credential-row-${cred.id}`}>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {deviceName(cred.device)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="info">
                          {CREDENTIAL_TYPE_LABELS[cred.credential_type] ?? cred.credential_type}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">
                        {cred.device_user_id}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                        {formatAccessTimestamp(cred.enrolled_at)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={cred.is_active ? "success" : "default"}>
                          {cred.is_active ? "Active" : "Deactivated"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {cred.is_active && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setConfirmTarget(cred)}
                            data-testid={`deactivate-credential-${cred.id}`}
                          >
                            Deactivate
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h3 className="text-base font-semibold text-gray-900">Recent attendance</h3>
          <p className="mt-0.5 text-sm text-gray-500">
            Check-ins recorded from biometric punches and manual entries.
          </p>
        </CardHeader>
        <CardBody className="p-0">
          {attendance.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-gray-500" data-testid="attendance-empty">
              No attendance records for this customer yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Date</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Check-in</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Check-out</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {recentAttendance(attendance).map((record) => (
                    <tr key={record.id} className="hover:bg-gray-50" data-testid={`attendance-row-${record.id}`}>
                      <td className="whitespace-nowrap px-4 py-3 font-medium text-gray-900">
                        {formatAttendanceDate(record.date)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                        {formatAttendanceTime(record.check_in_time)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                        {formatAttendanceTime(record.check_out_time)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setDialogOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Enroll biometric credential"
        >
          <div
            className="w-full max-w-lg rounded-xl bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
            data-testid="biometric-enroll-dialog"
          >
            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
              <h3 className="text-lg font-semibold text-gray-900">Enroll biometric</h3>
              <button
                onClick={() => setDialogOpen(false)}
                aria-label="Close"
                className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 px-6 py-5">
              {saveError != null && <Alert variant="error">{errorMessage(saveError)}</Alert>}

              <div className="space-y-1.5">
                <label htmlFor="biometric-enroll-device" className="block text-sm font-medium text-gray-700">
                  Device
                </label>
                <select
                  id="biometric-enroll-device"
                  aria-label="Device"
                  className={selectClass}
                  value={enrollDevice}
                  onChange={(e) => setEnrollDevice(e.target.value)}
                >
                  <option value="">Select a device</option>
                  {activeDevices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="biometric-enroll-type" className="block text-sm font-medium text-gray-700">
                  Credential type
                </label>
                <select
                  id="biometric-enroll-type"
                  aria-label="Credential type"
                  className={selectClass}
                  value={enrollType}
                  onChange={(e) => setEnrollType(e.target.value)}
                >
                  {ACCESS_CREDENTIAL_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {CREDENTIAL_TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
              </div>

              <p className="text-sm text-gray-500">
                The device user ID is assigned automatically — you&apos;ll see it right after
                enrolling to type on the device.
              </p>

              <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
                <Button variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={submitEnroll} loading={saving} data-testid="biometric-enroll-submit">
                  Enroll &amp; sync
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {confirmTarget && (
        <div data-testid="deactivate-confirm">
          <ConfirmDialog
            title="Deactivate credential?"
            confirmLabel="Deactivate"
            destructive
            busy={deactivating}
            onConfirm={submitDeactivate}
            onClose={() => setConfirmTarget(null)}
          >
            <p>
              This removes {deviceName(confirmTarget.device)}{" "}
              {CREDENTIAL_TYPE_LABELS[confirmTarget.credential_type].toLowerCase()} recognition for
              this member (device user ID{" "}
              <span className="font-mono">{confirmTarget.device_user_id}</span>). You can enroll
              again anytime.
            </p>
          </ConfirmDialog>
        </div>
      )}
    </div>
  );
}
