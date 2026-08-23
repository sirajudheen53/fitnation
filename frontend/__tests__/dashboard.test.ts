import { formatTrainerRevenue, formatTrainerRating } from "@/features/dashboard/components/TrainerOverview";
import { formatDueDate } from "@/features/dashboard/components/PendingPayments";

describe("TrainerOverview helpers", () => {
  it("formats revenue with rupee symbol", () => {
    expect(formatTrainerRevenue(32000)).toBe("₹32,000");
  });

  it("handles string revenue", () => {
    expect(formatTrainerRevenue("15000")).toBe("₹15,000");
  });

  it("formats rating to one decimal place", () => {
    expect(formatTrainerRating(4.5)).toBe("4.5");
  });

  it("returns em dash for invalid rating", () => {
    expect(formatTrainerRating("abc")).toBe("—");
  });
});

describe("PendingPayments helpers", () => {
  it("formats an ISO date to a locale string", () => {
    const formatted = formatDueDate("2026-05-10T00:00:00Z");
    expect(formatted).not.toBe("—");
    expect(formatted).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });

  it("returns an em dash for null dates", () => {
    expect(formatDueDate(null)).toBe("—");
  });
});
