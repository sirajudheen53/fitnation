"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type { Branch } from "@/types/branch";
import {
  ACCESS_CONNECTION_TYPES,
  ACCESS_VENDORS,
  CONNECTION_TYPE_LABELS,
  VENDOR_LABELS,
  type AccessDevice,
  type AccessDeviceFormData,
} from "@/types/access";

const deviceSchema = z.object({
  branch: z.coerce
    .number({ invalid_type_error: "Select a branch" })
    .positive("Select a branch"),
  name: z.string().min(1, "Device name is required"),
  vendor: z.enum(ACCESS_VENDORS, { message: "Select a vendor" }),
  model: z.string().min(1, "Model is required"),
  serial_number: z
    .string()
    .min(3, "Serial number must be at least 3 characters"),
  connection_type: z.enum(ACCESS_CONNECTION_TYPES, {
    message: "Select a connection type",
  }),
  api_endpoint: z.preprocess(
    (v) => (typeof v === "string" && v.trim() === "" ? undefined : v),
    z.string().url("Enter a valid URL (optional)").optional(),
  ),
  is_active: z.boolean(),
});

type DeviceSchemaData = z.infer<typeof deviceSchema>;

const EMPTY_DEFAULTS: DeviceSchemaData = {
  branch: 0,
  name: "",
  vendor: "generic",
  model: "",
  serial_number: "",
  connection_type: "webhook",
  api_endpoint: "",
  is_active: true,
};

const selectClass =
  "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

interface DeviceFormDialogProps {
  open: boolean;
  /** Device being edited, or null when adding. */
  device: AccessDevice | null;
  branches: Branch[];
  saving?: boolean;
  error?: unknown;
  onSubmit: (data: AccessDeviceFormData) => void | Promise<void>;
  onClose: () => void;
}

export function DeviceFormDialog({
  open,
  device,
  branches,
  saving = false,
  error,
  onSubmit,
  onClose,
}: DeviceFormDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<DeviceSchemaData>({
    resolver: zodResolver(deviceSchema),
    defaultValues: EMPTY_DEFAULTS,
  });

  // Re-seed the form each time the dialog opens (add vs. edit).
  useEffect(() => {
    if (!open) return;
    if (device) {
      reset({
        branch: device.branch,
        name: device.name,
        vendor: device.vendor,
        model: device.model,
        serial_number: device.serial_number,
        connection_type: device.connection_type,
        api_endpoint: device.api_endpoint || "",
        is_active: device.is_active,
      });
    } else {
      reset(EMPTY_DEFAULTS);
    }
  }, [open, device, reset]);

  if (!open) return null;

  const isActive = watch("is_active");

  const submit = handleSubmit((data) => {
    onSubmit({
      branch: data.branch,
      name: data.name,
      vendor: data.vendor,
      model: data.model,
      serial_number: data.serial_number,
      connection_type: data.connection_type,
      api_endpoint: data.api_endpoint ?? "",
      is_active: data.is_active,
    });
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={device ? "Edit device" : "Add device"}
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
        data-testid="device-form-dialog"
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">
            {device ? "Edit device" : "Add device"}
          </h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 px-6 py-5">
          {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="device-branch" className="block text-sm font-medium text-gray-700">
                Branch
              </label>
              <select
                id="device-branch"
                aria-label="Branch"
                className={selectClass}
                {...register("branch")}
              >
                <option value="">Select a branch</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
              {errors.branch && (
                <p className="text-sm text-red-600">{errors.branch.message}</p>
              )}
            </div>

            <Input
              label="Device name"
              placeholder="Main Entrance"
              error={errors.name?.message}
              {...register("name")}
            />

            <div className="space-y-1.5">
              <label htmlFor="device-vendor" className="block text-sm font-medium text-gray-700">
                Vendor
              </label>
              <select
                id="device-vendor"
                aria-label="Vendor"
                className={selectClass}
                {...register("vendor")}
              >
                {ACCESS_VENDORS.map((v) => (
                  <option key={v} value={v}>
                    {VENDOR_LABELS[v]}
                  </option>
                ))}
              </select>
              {errors.vendor && (
                <p className="text-sm text-red-600">{errors.vendor.message}</p>
              )}
            </div>

            <Input
              label="Model"
              placeholder="K40 Pro"
              error={errors.model?.message}
              {...register("model")}
            />

            <Input
              label="Serial number"
              placeholder="Device serial / MAC / IMEI"
              hint="Must be at least 3 characters."
              error={errors.serial_number?.message}
              {...register("serial_number")}
            />

            <div className="space-y-1.5">
              <label htmlFor="device-connection" className="block text-sm font-medium text-gray-700">
                Connection type
              </label>
              <select
                id="device-connection"
                aria-label="Connection type"
                className={selectClass}
                {...register("connection_type")}
              >
                {ACCESS_CONNECTION_TYPES.map((c) => (
                  <option key={c} value={c}>
                    {CONNECTION_TYPE_LABELS[c]}
                  </option>
                ))}
              </select>
              {errors.connection_type && (
                <p className="text-sm text-red-600">
                  {errors.connection_type.message}
                </p>
              )}
            </div>
          </div>

          <Input
            label="API endpoint (optional)"
            placeholder="https://device.local/api"
            hint="Device webhook or vendor cloud API URL."
            error={errors.api_endpoint?.message}
            {...register("api_endpoint")}
          />

          <label className="flex cursor-pointer items-center justify-between rounded-lg border border-gray-200 p-4">
            <div>
              <p className="text-sm font-medium text-gray-900">Device active</p>
              <p className="text-xs text-gray-500">
                Inactive devices are excluded from syncs and access checks.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={isActive}
              aria-label="Device active"
              onClick={() => setValue("is_active", !isActive, { shouldDirty: true })}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
                isActive ? "bg-brand-600" : "bg-gray-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  isActive ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </label>

          <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              {device ? "Save changes" : "Add device"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
