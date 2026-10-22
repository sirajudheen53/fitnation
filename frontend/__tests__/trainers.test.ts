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
} from "@/features/trainers/components/scheduleHelpers";
import type { Trainer } from "@/types/trainer";

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
