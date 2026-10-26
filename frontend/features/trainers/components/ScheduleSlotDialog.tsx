"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import { Button, Card, CardBody, Input } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import {
  DAY_OF_WEEK,
  type DayOfWeek,
  type ScheduleSlotInput,
  type TrainerScheduleSlot,
} from "@/types/trainer";
import { formatDayLabel, validateScheduleSlot } from "./scheduleHelpers";

const slotSchema = z.object({
  day_of_week: z.string().min(1, "Pick a day."),
  start_time: z.string().min(1, "Start time is required."),
  end_time: z.string().min(1, "End time is required."),
  is_available: z.boolean(),
});

type SlotFormValues = z.infer<typeof slotSchema>;

interface ScheduleSlotDialogProps {
  /** Present when editing an existing slot; null when creating. */
  slot: TrainerScheduleSlot | null;
  /** Pre-selected weekday when creating (per-day "Add" affordances). */
  defaultDay?: DayOfWeek;
  /** The trainer's current slots — duplicate-day (overlap) validation. */
  slots: TrainerScheduleSlot[];
  saving?: boolean;
  /** Submits the slot; throwing (e.g. a DRF 400) surfaces on the form. */
  onSubmit: (data: ScheduleSlotInput) => Promise<void>;
  onClose: () => void;
}

/** <input type="time"> only accepts "HH:MM" (or "HH:MM" with seconds step) —
 * the backend echoes "HH:MM:SS", so trim before prefilling. */
function toTimeInput(value: string): string {
  return value.slice(0, 5);
}

/**
 * Create/edit one weekly schedule slot (issue #80).
 *
 * The backend stores one window per (trainer, weekday): a duplicate day is
 * rejected client-side here and, as a backstop, server-side by a unique
 * constraint whose 400 surfaces on the form.
 */
export function ScheduleSlotDialog({
  slot,
  defaultDay,
  slots,
  saving = false,
  onSubmit,
  onClose,
}: ScheduleSlotDialogProps) {
  const editing = slot !== null;
  const [apiError, setApiError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<SlotFormValues>({
    resolver: zodResolver(slotSchema),
    defaultValues: {
      day_of_week: slot?.day_of_week ?? defaultDay ?? "monday",
      start_time: slot ? toTimeInput(slot.start_time) : "",
      end_time: slot ? toTimeInput(slot.end_time) : "",
      is_available: slot?.is_available ?? true,
    },
  });

  async function submit(values: SlotFormValues) {
    setApiError(null);
    setFieldErrors({});
    const input: ScheduleSlotInput = {
      day_of_week: values.day_of_week as DayOfWeek,
      start_time: values.start_time,
      end_time: values.end_time,
      is_available: values.is_available,
    };
    const issue = validateScheduleSlot(input, slots, slot?.id);
    if (issue) {
      setError(issue.field, { message: issue.message });
      return;
    }
    try {
      await onSubmit(input);
    } catch (err) {
      // Surface DRF field errors on their inputs; everything else as a banner.
      const data = (err as { data?: unknown }).data;
      if (data && typeof data === "object" && !Array.isArray(data)) {
        const entries = Object.entries(data as Record<string, unknown>).filter(
          ([key]) => key !== "detail" && key !== "trainer",
        );
        if (entries.length) {
          setFieldErrors(
            Object.fromEntries(
              entries.map(([k, v]) => [k, Array.isArray(v) ? v.map(String) : [String(v)]]),
            ),
          );
          return;
        }
      }
      setApiError(errorMessage(err));
    }
  }

  const dayError = errors.day_of_week?.message ?? fieldErrors.day_of_week?.[0];
  const startError = errors.start_time?.message ?? fieldErrors.start_time?.[0];
  const endError = errors.end_time?.message ?? fieldErrors.end_time?.[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              {editing ? "Edit schedule slot" : "Add schedule slot"}
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
            {(apiError || fieldErrors.non_field_errors?.[0]) && (
              <p className="text-sm text-red-600" role="alert">
                {fieldErrors.non_field_errors?.[0] ?? apiError}
              </p>
            )}

            <div className="space-y-1.5">
              <label
                htmlFor="slot-day"
                className="block text-sm font-medium text-gray-700"
              >
                Day
              </label>
              <select
                id="slot-day"
                aria-label="Day of week"
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                {...register("day_of_week")}
              >
                {DAY_OF_WEEK.map((day) => (
                  <option key={day} value={day}>
                    {formatDayLabel(day)}
                  </option>
                ))}
              </select>
              {dayError && <p className="text-sm text-red-600">{dayError}</p>}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Start time"
                type="time"
                error={startError}
                {...register("start_time")}
              />
              <Input
                label="End time"
                type="time"
                error={endError}
                {...register("end_time")}
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                {...register("is_available")}
              />
              Available — the trainer takes bookings in this window
            </label>

            <div className="flex justify-end gap-2">
              <Button variant="outline" type="button" onClick={onClose} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving} data-testid="schedule-slot-submit">
                {editing ? "Save changes" : "Add slot"}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
