import {
  getAttendanceStatusLabel,
  formatTime,
} from "@/features/attendance/components/AttendanceTable";

describe("AttendanceTable helpers", () => {
  it("returns the correct label for each attendance status", () => {
    expect(getAttendanceStatusLabel("present")).toBe("Present");
    expect(getAttendanceStatusLabel("late")).toBe("Late");
    expect(getAttendanceStatusLabel("absent")).toBe("Absent");
    expect(getAttendanceStatusLabel("left")).toBe("Left");
  });

  it("formats an ISO time to HH:MM", () => {
    const formatted = formatTime("2026-04-01T09:30:00Z");
    expect(formatted).toMatch(/^\d{1,2}:\d{2}\s?(AM|PM)$/i);
  });

  it("returns an em dash for null times", () => {
    expect(formatTime(null)).toBe("—");
  });
});
