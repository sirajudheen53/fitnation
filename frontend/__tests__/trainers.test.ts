import {
  formatRating,
  formatRevenue,
} from "@/features/trainers/components/TrainerCard";
import {
  formatDayName,
  formatTime,
} from "@/features/trainers/components/scheduleHelpers";

describe("TrainerCard helpers", () => {
  it("formats rating to one decimal place", () => {
    expect(formatRating(4.56)).toBe("4.6");
  });

  it("handles string ratings", () => {
    expect(formatRating("4.2")).toBe("4.2");
  });

  it("returns em dash for invalid rating", () => {
    expect(formatRating("abc")).toBe("—");
  });

  it("formats revenue with rupee symbol", () => {
    expect(formatRevenue(25000)).toBe("₹25,000");
  });
});

describe("Schedule helpers", () => {
  it("returns the correct day name", () => {
    expect(formatDayName(0)).toBe("Sunday");
    expect(formatDayName(3)).toBe("Wednesday");
    expect(formatDayName(6)).toBe("Saturday");
  });

  it("formats a time string to HH:MM", () => {
    const formatted = formatTime("09:30:00");
    expect(formatted).toMatch(/^\d{1,2}:\d{2}\s?(AM|PM)$/i);
  });
});
