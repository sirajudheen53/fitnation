import {
  getCustomerDisplayName,
  getCustomerMembershipStatus,
} from "@/features/customers/components/CustomerTable";
import { calculateBmi } from "@/features/customers/components/HealthProfileForm";

describe("CustomerTable helpers", () => {
  it("returns full name when first and last name are present", () => {
    const customer = {
      id: 1,
      user_id: 1,
      email: "test@example.com",
      first_name: "Arjun",
      last_name: "Kumar",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    expect(getCustomerDisplayName(customer)).toBe("Arjun Kumar");
  });

  it("falls back to email when names are missing", () => {
    const customer = {
      id: 2,
      user_id: 2,
      email: "only@email.com",
      first_name: "",
      last_name: "",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    expect(getCustomerDisplayName(customer)).toBe("only@email.com");
  });

  it("marks active customers as Active", () => {
    const customer = {
      id: 3,
      user_id: 3,
      email: "active@example.com",
      first_name: "Active",
      last_name: "User",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    expect(getCustomerMembershipStatus(customer)).toEqual({
      label: "Active",
      variant: "success",
    });
  });

  it("marks inactive customers as Inactive", () => {
    const customer = {
      id: 4,
      user_id: 4,
      email: "inactive@example.com",
      first_name: "Inactive",
      last_name: "User",
      is_active: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    expect(getCustomerMembershipStatus(customer)).toEqual({
      label: "Inactive",
      variant: "danger",
    });
  });
});

describe("HealthProfileForm BMI helper", () => {
  it("calculates BMI from height and weight", () => {
    expect(calculateBmi(180, 75)).toBeCloseTo(23.1, 1);
  });

  it("returns undefined when height is missing", () => {
    expect(calculateBmi(undefined, 75)).toBeUndefined();
  });

  it("returns undefined when weight is missing", () => {
    expect(calculateBmi(180, undefined)).toBeUndefined();
  });

  it("returns undefined for non-positive height", () => {
    expect(calculateBmi(0, 75)).toBeUndefined();
  });
});
