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
