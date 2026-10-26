import type { DayOfWeek, TrainerScheduleSlot } from "@/types/trainer";

const DAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

/** Backend day keys (users.TrainerSchedule.DayOfWeek) → display names. */
const DAY_KEY_NAMES: Record<string, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};

export function formatDayName(day: number): string {
  return DAY_NAMES[day] ?? String(day);
}

/** "monday" → "Monday"; unknown keys pass through. */
export function formatDayLabel(day: string): string {
  return DAY_KEY_NAMES[day] ?? day;
}

export function formatTime(time: string): string {
  return new Date(`1970-01-01T${time}`).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTimeRange(start: string, end: string): string {
  return `${formatTime(start)} – ${formatTime(end)}`;
}

/**
 * Client-side schedule-slot validation (issue #80).
 *
 * The backend keeps exactly one schedule row per (trainer, day_of_week), so
 * two slots can never genuinely overlap — a conflict is a duplicate weekday
 * (or a window that ends before it starts). Returns the offending field with
 * a human-readable message, or null when the slot is acceptable. Server 400s
 * remain the backstop; this only pre-empts calls we already know are invalid.
 */
export interface ScheduleSlotIssue {
  field: "end_time" | "day_of_week";
  message: string;
}

export function validateScheduleSlot(
  input: { day_of_week: DayOfWeek; start_time: string; end_time: string },
  existingSlots: TrainerScheduleSlot[],
  currentSlotId?: number,
): ScheduleSlotIssue | null {
  if (!input.start_time || !input.end_time) return null;
  if (input.end_time <= input.start_time) {
    return { field: "end_time", message: "End time must be after start time." };
  }
  const clash = existingSlots.find(
    (slot) => slot.day_of_week === input.day_of_week && slot.id !== currentSlotId,
  );
  if (clash) {
    return {
      field: "day_of_week",
      message: `A slot already exists for ${formatDayLabel(input.day_of_week)} — edit that slot instead.`,
    };
  }
  return null;
}
