import {
  certificationLabel,
  formatRating,
  resolveTrainerPhoto,
  trainerInitials,
  trainerName,
} from "@/features/trainers/components/trainers-shared";
import {
  formatDayLabel,
  formatDayName,
  formatTime,
  validateScheduleSlot,
} from "@/features/trainers/components/scheduleHelpers";
import type { Trainer, TrainerScheduleSlot } from "@/types/trainer";

const sampleTrainer = (overrides: Partial<Trainer> = {}): Trainer => ({
  id: 1,
  user_id: 11,
  email: "asha@fit.test",
  first_name: "Asha",
  last_name: "Menon",
  phone: null,
  specialization: "Strength",
  bio: null,
  is_active: true,
  certifications: [],
  experience_years: 5,
  rating: "4.25",
  profile_photo: "",
  max_clients: 20,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("trainers-shared helpers", () => {
  it("formats rating to one decimal place", () => {
    expect(formatRating(4.56)).toBe("4.6");
    expect(formatRating("4.25")).toBe("4.3");
  });

  it("returns em dash for missing or invalid rating", () => {
    expect(formatRating("abc")).toBe("—");
    expect(formatRating(null)).toBe("—");
  });

  it("builds display name falling back to email", () => {
    expect(trainerName(sampleTrainer())).toBe("Asha Menon");
    expect(trainerName(sampleTrainer({ first_name: "", last_name: "" }))).toBe(
      "asha@fit.test",
    );
  });

  it("builds initials with a question-mark fallback", () => {
    expect(trainerInitials(sampleTrainer())).toBe("AM");
    expect(trainerInitials(sampleTrainer({ first_name: "", last_name: "" }))).toBe("?");
  });

  it("labels string certifications as-is", () => {
    expect(certificationLabel("ACE-CPT")).toBe("ACE-CPT");
  });

  it("labels object certifications from name/issuer/year", () => {
    expect(
      certificationLabel({ name: "ACE-CPT", issuer: "ACE", year: 2021 }),
    ).toBe("ACE-CPT — ACE — 2021");
    expect(certificationLabel({})).toBe("Certification");
  });

  it("resolves profile photo URLs and empty values", () => {
    expect(
      resolveTrainerPhoto(sampleTrainer({ profile_photo: "https://cdn/x.jpg" })),
    ).toBe("https://cdn/x.jpg");
    expect(resolveTrainerPhoto(sampleTrainer())).toBeNull();
  });
});

describe("Schedule helpers", () => {
  it("returns the correct day name", () => {
    expect(formatDayName(0)).toBe("Sunday");
    expect(formatDayName(3)).toBe("Wednesday");
    expect(formatDayName(6)).toBe("Saturday");
  });

  it("labels backend day keys", () => {
    expect(formatDayLabel("monday")).toBe("Monday");
    expect(formatDayLabel("sunday")).toBe("Sunday");
    expect(formatDayLabel("funday")).toBe("funday");
  });

  it("formats a time string to HH:MM", () => {
    const formatted = formatTime("09:30:00");
    expect(formatted).toMatch(/^\d{1,2}:\d{2}\s?(AM|PM)$/i);
  });
});

describe("validateScheduleSlot (issue #80)", () => {
  const slot = (overrides: Partial<TrainerScheduleSlot> = {}): TrainerScheduleSlot => ({
    id: 7,
    trainer: 1,
    day_of_week: "monday",
    start_time: "06:00:00",
    end_time: "10:00:00",
    is_available: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  });

  it("accepts a window on a free day", () => {
    expect(
      validateScheduleSlot(
        { day_of_week: "tuesday", start_time: "08:00", end_time: "10:00" },
        [slot()],
      ),
    ).toBeNull();
  });

  it("rejects a window that ends before it starts", () => {
    expect(
      validateScheduleSlot(
        { day_of_week: "tuesday", start_time: "10:00", end_time: "08:00" },
        [],
      ),
    ).toEqual({ field: "end_time", message: "End time must be after start time." });
  });

  it("rejects equal start and end times", () => {
    expect(
      validateScheduleSlot(
        { day_of_week: "tuesday", start_time: "08:00", end_time: "08:00" },
        [],
      )?.field,
    ).toBe("end_time");
  });

  it("rejects a duplicate weekday — the only overlap the one-slot-per-day model allows", () => {
    expect(
      validateScheduleSlot(
        { day_of_week: "monday", start_time: "12:00", end_time: "14:00" },
        [slot()],
      ),
    ).toEqual({
      field: "day_of_week",
      message: "A slot already exists for Monday — edit that slot instead.",
    });
  });

  it("ignores the slot being edited when checking duplicate days", () => {
    expect(
      validateScheduleSlot(
        { day_of_week: "monday", start_time: "06:00", end_time: "11:00" },
        [slot()],
        7,
      ),
    ).toBeNull();
  });

  it("defers empty times to required-field validation", () => {
    expect(
      validateScheduleSlot({ day_of_week: "monday", start_time: "", end_time: "" }, []),
    ).toBeNull();
  });
});
