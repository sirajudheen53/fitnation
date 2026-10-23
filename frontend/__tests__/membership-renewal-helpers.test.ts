/**
 * Unit tests for the renewal preview helpers shared by the memberships page
 * and the customer-detail membership card.
 */
import {
  RENEWAL_FALLBACK_DAYS,
  addDaysISO,
  renewalDays,
  renewalNewEndDate,
} from "@/features/memberships/lib/renewal";
import type { Membership, MembershipPlan } from "@/types/membership";

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan => ({
  id: 2,
  name: "Gold",
  price: "1999.00",
  duration_days: 30,
  plan_type: "monthly",
  description: null,
  is_active: true,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

const membership = (overrides: Partial<Membership> = {}): Membership => ({
  id: 1,
  customer_id: 1,
  customer_name: "Meera Nair",
  plan_id: 2,
  plan_name: "Gold",
  start_date: "2026-04-01",
  end_date: "2026-09-30",
  status: "expired",
  price: 1999,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-01T00:00:00Z",
  ...overrides,
});

describe("addDaysISO", () => {
  it("shifts an ISO date by N days across month boundaries", () => {
    expect(addDaysISO("2026-09-30", 30)).toBe("2026-10-30");
    expect(addDaysISO("2026-12-15", 30)).toBe("2027-01-14");
    expect(addDaysISO("2026-01-01", 0)).toBe("2026-01-01");
  });

  it("returns null for an unusable date", () => {
    expect(addDaysISO("not-a-date", 30)).toBeNull();
  });
});

describe("renewalDays", () => {
  it("uses the membership plan's duration", () => {
    expect(renewalDays(membership(), [plan({ duration_days: 90 })])).toBe(90);
  });

  it("falls back to 30 days when the plan is missing", () => {
    expect(renewalDays(membership({ plan_id: 999 }), [plan()])).toBe(
      RENEWAL_FALLBACK_DAYS,
    );
    expect(renewalDays(membership(), [])).toBe(RENEWAL_FALLBACK_DAYS);
  });
});

/* Issue #68: renewing onto a DIFFERENT plan — the preview must use the
 * selected plan's duration, not the membership's current one. */
describe("renewalDays plan override", () => {
  const plans = [
    plan({ duration_days: 30 }),
    plan({ id: 3, name: "Platinum", duration_days: 90, plan_type: "quarterly" }),
  ];

  it("uses the overridden plan's duration", () => {
    expect(renewalDays(membership(), plans, 3)).toBe(90);
  });

  it("keeps current-plan behavior when the override is undefined", () => {
    expect(renewalDays(membership(), plans, undefined)).toBe(30);
  });

  it("falls back to 30 when the overridden plan isn't in the list", () => {
    expect(renewalDays(membership(), [plan()], 999)).toBe(
      RENEWAL_FALLBACK_DAYS,
    );
  });
});

describe("renewalNewEndDate", () => {
  it("computes end_date + plan duration", () => {
    expect(renewalNewEndDate(membership(), [plan({ duration_days: 30 })])).toBe(
      "2026-10-30",
    );
  });

  it("returns null when the end date isn't a usable date", () => {
    expect(renewalNewEndDate(membership({ end_date: "" }), [plan()])).toBeNull();
  });

  it("uses the overridden plan's duration (issue #68)", () => {
    expect(
      renewalNewEndDate(
        membership(),
        [plan(), plan({ id: 3, duration_days: 90 })],
        3,
      ),
    ).toBe("2026-12-29");
  });
});
