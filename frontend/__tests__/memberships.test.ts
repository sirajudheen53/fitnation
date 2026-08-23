import {
  getMembershipStatusLabel,
  formatMembershipDate,
} from "@/features/memberships/components/MembershipTable";

describe("MembershipTable helpers", () => {
  it("returns the correct label for each status", () => {
    expect(getMembershipStatusLabel("active")).toBe("Active");
    expect(getMembershipStatusLabel("pending")).toBe("Pending");
    expect(getMembershipStatusLabel("expired")).toBe("Expired");
    expect(getMembershipStatusLabel("cancelled")).toBe("Cancelled");
  });

  it("formats an ISO date to a locale string", () => {
    const formatted = formatMembershipDate("2026-01-15T00:00:00Z");
    expect(formatted).not.toBe("—");
    expect(formatted).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });

  it("returns an em dash for null dates", () => {
    expect(formatMembershipDate(null)).toBe("—");
  });
});
