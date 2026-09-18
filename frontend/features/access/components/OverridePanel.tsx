"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ShieldCheck, ShieldX, History } from "lucide-react";
import { Alert, Badge, Button, Card, CardBody, CardHeader, Input } from "@/components/ui";
import { getCustomerDisplayName } from "@/features/customers/components/CustomerTable";
import { errorMessage } from "@/lib/api";
import type { Customer } from "@/types/customer";
import {
  formatAccessTimestamp,
  ACCESS_OVERRIDE_REASONS,
  OVERRIDE_REASON_OPTIONS,
  OVERRIDE_REASON_LABELS,
  type AccessDevice,
  type AccessOverride,
  type AccessOverrideFormData,
} from "@/types/access";

const overrideSchema = z.object({
  customer: z.coerce
    .number({ invalid_type_error: "Select a customer" })
    .positive("Select a customer"),
  device: z.coerce
    .number({ invalid_type_error: "Select a device" })
    .positive("Select a device"),
  allow_access: z.boolean(),
  reason: z.enum(ACCESS_OVERRIDE_REASONS, {
    message: "Select a reason",
  }),
  reason_notes: z.string().optional(),
  expires_at: z.string().optional(),
});

type OverrideSchemaData = z.infer<typeof overrideSchema>;

const selectClass =
  "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

interface OverridePanelProps {
  overrides: AccessOverride[];
  customers: Customer[];
  devices: AccessDevice[];
  saving?: boolean;
  error?: unknown;
  onSubmit: (data: AccessOverrideFormData) => void | Promise<void>;
}

export function OverridePanel({
  overrides,
  customers,
  devices,
  saving = false,
  error,
  onSubmit,
}: OverridePanelProps) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    formState: { errors },
  } = useForm<OverrideSchemaData>({
    resolver: zodResolver(overrideSchema),
    defaultValues: {
      customer: 0,
      device: 0,
      allow_access: true,
      reason: "grace_period",
      reason_notes: "",
      expires_at: "",
    },
  });

  const allowAccess = watch("allow_access");

  const customerName = (id: number) => {
    const match = customers.find((c) => c.id === id);
    return match ? getCustomerDisplayName(match) : `Customer #${id}`;
  };

  const deviceName = (id: number) =>
    devices.find((d) => d.id === id)?.name ?? `Device #${id}`;

  const submit = handleSubmit((data) => {
    // datetime-local ("2026-09-18T10:30") → ISO-8601 for the backend.
    const expires = data.expires_at ? new Date(data.expires_at).toISOString() : null;
    onSubmit({
      customer: data.customer,
      device: data.device,
      allow_access: data.allow_access,
      reason: data.reason,
      reason_notes: data.reason_notes ?? "",
      expires_at: expires,
    });
    reset({
      customer: 0,
      device: 0,
      allow_access: true,
      reason: "grace_period",
      reason_notes: "",
      expires_at: "",
    });
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h3 className="text-base font-semibold text-gray-900">Grant / revoke access</h3>
          <p className="mt-0.5 text-sm text-gray-500">
            Overrides take precedence over membership checks at a specific device.
          </p>
        </CardHeader>
        <CardBody>
          <form onSubmit={submit} className="space-y-4" data-testid="override-form">
            {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="override-customer" className="block text-sm font-medium text-gray-700">
                  Customer
                </label>
                <select
                  id="override-customer"
                  aria-label="Customer"
                  className={selectClass}
                  {...register("customer")}
                >
                  <option value="">Select a customer</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {getCustomerDisplayName(c)}
                    </option>
                  ))}
                </select>
                {errors.customer && (
                  <p className="text-sm text-red-600">{errors.customer.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="override-device" className="block text-sm font-medium text-gray-700">
                  Device
                </label>
                <select
                  id="override-device"
                  aria-label="Device"
                  className={selectClass}
                  {...register("device")}
                >
                  <option value="">Select a device</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
                {errors.device && (
                  <p className="text-sm text-red-600">{errors.device.message}</p>
                )}
              </div>

              <Controller
                control={control}
                name="allow_access"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <span className="block text-sm font-medium text-gray-700">Access</span>
                    <div className="flex gap-2" role="group" aria-label="Access">
                      <button
                        type="button"
                        aria-pressed={field.value === true}
                        onClick={() => field.onChange(true)}
                        className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
                          field.value
                            ? "border-green-600 bg-green-50 text-green-700"
                            : "border-gray-300 bg-white text-gray-600 hover:bg-gray-50"
                        }`}
                        data-testid="override-allow-btn"
                      >
                        <ShieldCheck className="h-4 w-4" /> Allow
                      </button>
                      <button
                        type="button"
                        aria-pressed={field.value === false}
                        onClick={() => field.onChange(false)}
                        className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
                          field.value === false
                            ? "border-red-600 bg-red-50 text-red-700"
                            : "border-gray-300 bg-white text-gray-600 hover:bg-gray-50"
                        }`}
                        data-testid="override-deny-btn"
                      >
                        <ShieldX className="h-4 w-4" /> Deny
                      </button>
                    </div>
                  </div>
                )}
              />

              <div className="space-y-1.5">
                <label htmlFor="override-reason" className="block text-sm font-medium text-gray-700">
                  Reason
                </label>
                <select
                  id="override-reason"
                  aria-label="Reason"
                  className={selectClass}
                  {...register("reason")}
                >
                  {OVERRIDE_REASON_OPTIONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
                {errors.reason && (
                  <p className="text-sm text-red-600">{errors.reason.message}</p>
                )}
              </div>

              <Input
                label="Notes (optional)"
                placeholder={allowAccess ? "e.g. renewal due next week" : "e.g. dues pending"}
                {...register("reason_notes")}
              />

              <Input
                label="Expires at (optional)"
                type="datetime-local"
                hint="Leave blank for a permanent override."
                {...register("expires_at")}
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" loading={saving}>
                {allowAccess ? "Grant access" : "Deny access"}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-gray-400" />
            <h3 className="text-base font-semibold text-gray-900">Override history</h3>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          {overrides.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-gray-500" data-testid="override-history-empty">
              No overrides recorded yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Customer</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Device</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Access</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Reason</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Notes</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Expires</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {overrides.map((o) => (
                    <tr key={o.id} className="hover:bg-gray-50" data-testid={`override-row-${o.id}`}>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {customerName(o.customer)}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{deviceName(o.device)}</td>
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
    </div>
  );
}
