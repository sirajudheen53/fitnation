"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { QrCode, User, Building2, Clock } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { AttendanceType, CheckInData } from "@/types/attendance";
import { errorMessage } from "@/lib/api";

const checkInSchema = z.object({
  person_id: z.coerce.number().int().positive("Enter a member or trainer ID"),
  person_type: z.enum(["customer", "trainer", "staff"]),
  branch_id: z.coerce.number().int().positive().optional().or(z.nan().transform(() => undefined)),
  status: z.enum(["present", "late", "absent", "left"]).optional(),
});

type CheckInSchemaData = z.infer<typeof checkInSchema>;

interface CheckInFormProps {
  onSubmit: (data: CheckInData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
  submitLabel?: string;
}

export function CheckInForm({
  onSubmit,
  error,
  loading = false,
  submitLabel = "Check in",
}: CheckInFormProps) {
  const [qrMode, setQrMode] = useState(false);
  const [qrCode, setQrCode] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CheckInSchemaData>({
    resolver: zodResolver(checkInSchema),
    defaultValues: {
      person_id: undefined,
      person_type: "customer",
      branch_id: undefined,
      status: "present",
    },
  });

  const handleFormSubmit = async (data: CheckInSchemaData) => {
    const payload: CheckInData = {
      person_id: data.person_id,
      person_type: data.person_type,
      branch_id:
        data.branch_id !== undefined && !Number.isNaN(data.branch_id)
          ? data.branch_id
          : undefined,
      status: data.status ?? undefined,
    };
    await onSubmit(payload);
  };

  const handleQrScan = () => {
    const match = qrCode.match(/\d+/);
    if (match) {
      reset({ person_id: Number(match[0]), person_type: "customer", branch_id: undefined, status: "present" });
      setQrMode(false);
      setQrCode("");
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      {/* Mode toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setQrMode(false)}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${
            !qrMode ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-700"
          }`}
        >
          Manual entry
        </button>
        <button
          type="button"
          onClick={() => setQrMode(true)}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${
            qrMode ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-700"
          }`}
        >
          <span className="inline-flex items-center gap-2">
            <QrCode className="h-4 w-4" /> QR scan
          </span>
        </button>
      </div>

      {qrMode ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-10 text-center">
          <QrCode className="mx-auto h-16 w-16 text-gray-400" />
          <p className="mt-4 text-sm text-gray-600">
            Point the scanner at the member&apos;s QR code, or paste the QR payload below.
          </p>
          <div className="mx-auto mt-4 max-w-md">
            <Input
              placeholder="QR code / member ID"
              value={qrCode}
              onChange={(e) => setQrCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQrScan()}
              icon={<QrCode className="h-4 w-4" />}
            />
          </div>
          <Button
            className="mt-4"
            variant="outline"
            onClick={handleQrScan}
          >
            Use QR code
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Member / Trainer ID"
              type="number"
              min="1"
              placeholder="1"
              icon={<User className="h-4 w-4" />}
              error={errors.person_id?.message}
              {...register("person_id")}
            />

            <div className="space-y-1.5">
              <label htmlFor="person_type" className="block text-sm font-medium text-gray-700">
                Person type
              </label>
              <div className="relative">
                <Clock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <select
                  id="person_type"
                  {...register("person_type")}
                  className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="customer">Customer</option>
                  <option value="trainer">Trainer</option>
                  <option value="staff">Staff</option>
                </select>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Branch ID (optional)"
              type="number"
              min="1"
              placeholder="1"
              error={errors.branch_id?.message}
              {...register("branch_id")}
            />

            <div className="space-y-1.5">
              <label htmlFor="status" className="block text-sm font-medium text-gray-700">
                Status
              </label>
              <select
                id="status"
                {...register("status")}
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="present">Present</option>
                <option value="late">Late</option>
                <option value="absent">Absent</option>
                <option value="left">Left</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button type="submit" loading={loading}>
              {submitLabel}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
