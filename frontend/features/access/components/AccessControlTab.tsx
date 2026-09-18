"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Fingerprint, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { Alert, Badge, Button, Card, CardBody, CardHeader, Input, Spinner } from "@/components/ui";
import { getToken } from "@/lib/auth";
import {
  enrollBiometricCredential,
  fetchAccessCredentials,
  fetchAccessOverrides,
  fetchDevices,
  errorMessage,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import {
  ACCESS_CREDENTIAL_TYPES,
  CREDENTIAL_TYPE_LABELS,
  formatAccessTimestamp,
  OVERRIDE_REASON_LABELS,
  type AccessCredential,
  type AccessDevice,
  type AccessOverride,
} from "@/types/access";

const enrollSchema = z.object({
  device: z.coerce
    .number({ invalid_type_error: "Select a device" })
    .positive("Select a device"),
  credential_type: z.enum(ACCESS_CREDENTIAL_TYPES, {
    message: "Select a credential type",
  }),
  device_user_id: z.string().min(1, "Device user ID is required"),
});

type EnrollSchemaData = z.infer<typeof enrollSchema>;

const selectClass =
  "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

interface AccessControlTabProps {
  customer: Customer;
}

export function AccessControlTab({ customer }: AccessControlTabProps) {
  const [devices, setDevices] = useState<AccessDevice[]>([]);
  const [credentials, setCredentials] = useState<AccessCredential[]>([]);
  const [overrides, setOverrides] = useState<AccessOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EnrollSchemaData>({
    resolver: zodResolver(enrollSchema),
    defaultValues: {
      device: 0,
      credential_type: "fingerprint",
      device_user_id: "",
    },
  });

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;

    async function load() {
      try {
        const [creds, ovs, devs] = await Promise.all([
          fetchAccessCredentials(authToken, { customer: customer.id }),
          fetchAccessOverrides(authToken, { customer: customer.id }),
          fetchDevices(authToken),
        ]);
        setCredentials(creds);
        setOverrides(ovs);
        setDevices(devs);
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

  const openDialog = () => {
    reset({ device: 0, credential_type: "fingerprint", device_user_id: "" });
    setSaveError(null);
    setDialogOpen(true);
  };

  const submitEnroll = handleSubmit(async (data) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const result = await enrollBiometricCredential(
        {
          customer: customer.id,
          device: data.device,
          credential_type: data.credential_type,
          device_user_id: data.device_user_id,
        },
        token,
      );
      setCredentials((prev) => [result.credential, ...prev]);
      setDialogOpen(false);
      toast.success(
        `Enrolled on ${deviceName(data.device)} · ${result.sync.detail ?? "synced"}`,
      );
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  });

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const activeDevices = devices.filter((d) => d.is_active);

  return (
    <div className="space-y-6">
      {error && <Alert variant="error">{error}</Alert>}

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Fingerprint className="h-4 w-4 text-gray-400" />
            <h3 className="text-base font-semibold text-gray-900">Biometric credentials</h3>
          </div>
          <Button
            size="sm"
            onClick={openDialog}
            disabled={activeDevices.length === 0}
            data-testid="enroll-biometric-btn"
          >
            <Plus className="h-4 w-4" /> Enroll biometric
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
                          {cred.is_active ? "Active" : "Revoked"}
                        </Badge>
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
          <h3 className="text-base font-semibold text-gray-900">Access overrides</h3>
          <p className="mt-0.5 text-sm text-gray-500">
            Owner grant/deny rules for this customer (managed on the Access Devices page).
          </p>
        </CardHeader>
        <CardBody className="p-0">
          {overrides.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-gray-500" data-testid="overrides-empty">
              No overrides for this customer.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Device</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Access</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Reason</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Notes</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Expires</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {overrides.map((o) => (
                    <tr key={o.id} className="hover:bg-gray-50" data-testid={`customer-override-row-${o.id}`}>
                      <td className="px-4 py-3 font-medium text-gray-900">{deviceName(o.device)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={o.allow_access ? "success" : "danger"}>
                          {o.allow_access ? "Allow" : "Deny"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {OVERRIDE_REASON_LABELS[o.reason] ?? o.reason}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{o.reason_notes || "—"}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {o.expires_at ? formatAccessTimestamp(o.expires_at) : "Permanent"}
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
            data-testid="enroll-dialog"
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

            <form onSubmit={submitEnroll} className="space-y-4 px-6 py-5">
              {saveError != null && <Alert variant="error">{errorMessage(saveError)}</Alert>}

              <div className="space-y-1.5">
                <label htmlFor="enroll-device" className="block text-sm font-medium text-gray-700">
                  Device
                </label>
                <select
                  id="enroll-device"
                  aria-label="Device"
                  className={selectClass}
                  {...register("device")}
                >
                  <option value="">Select a device</option>
                  {activeDevices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
                {errors.device && (
                  <p className="text-sm text-red-600">{errors.device.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="enroll-type" className="block text-sm font-medium text-gray-700">
                  Credential type
                </label>
                <select
                  id="enroll-type"
                  aria-label="Credential type"
                  className={selectClass}
                  {...register("credential_type")}
                >
                  {ACCESS_CREDENTIAL_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {CREDENTIAL_TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
                {errors.credential_type && (
                  <p className="text-sm text-red-600">{errors.credential_type.message}</p>
                )}
              </div>

              <Input
                label="Device user ID"
                placeholder="e.g. 42"
                hint="User ID assigned on the device (unique per device)."
                error={errors.device_user_id?.message}
                {...register("device_user_id")}
              />

              <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" loading={saving} data-testid="enroll-submit-btn">
                  Enroll &amp; sync
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
