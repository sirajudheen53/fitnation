/**
 * Phone E.164 helpers (issue #88) — mirror of the backend's India-default
 * storage rule (apps/users/phone.py) for the dashboard side.
 */
import {
  displayPhone,
  formatPhoneE164,
  isValidPhoneE164,
  parsePhoneInput,
  phoneDigits,
  samePhoneNumber,
} from "@/lib/phone";
import { findCountryByIso } from "@/lib/phoneCountries";

describe("parsePhoneInput", () => {
  it("splits an E.164 value on the dial code", () => {
    expect(parsePhoneInput("+919876543210")).toEqual({
      country: findCountryByIso("IN"),
      national: "9876543210",
    });
    expect(parsePhoneInput("+971501234567")).toEqual({
      country: findCountryByIso("AE"),
      national: "501234567",
    });
  });

  it("matches the longest dial code", () => {
    // "1" (US) vs "91" (IN) — +91… must not parse as US with national 1…
    const parsed = parsePhoneInput("+919876543210");
    expect(parsed.country.iso).toBe("IN");
  });

  it("lands bare legacy values on the India default with digits intact", () => {
    expect(parsePhoneInput("8606806956")).toEqual({
      country: findCountryByIso("IN"),
      national: "8606806956",
    });
    expect(parsePhoneInput("+91 98765 43210")).toEqual({
      country: findCountryByIso("IN"),
      national: "9876543210",
    });
  });

  it("keeps digits for unknown country codes instead of losing them", () => {
    const parsed = parsePhoneInput("+9991234567");
    expect(parsed.country.iso).toBe("IN");
    expect(parsed.national).toBe("9991234567");
  });

  it("returns the default country and empty digits for blank input", () => {
    expect(parsePhoneInput("")).toEqual({
      country: findCountryByIso("IN"),
      national: "",
    });
    expect(parsePhoneInput(null).national).toBe("");
  });
});

describe("formatPhoneE164", () => {
  it("composes +dial+national and stays blank when digits are blank", () => {
    expect(formatPhoneE164("91", "9876543210")).toBe("+919876543210");
    expect(formatPhoneE164("91", "")).toBe("");
    expect(formatPhoneE164("971", "50-123 4567")).toBe("+971501234567");
  });
});

describe("isValidPhoneE164", () => {
  it("accepts the canonical shape", () => {
    expect(isValidPhoneE164("+919876543210")).toBe(true);
    expect(isValidPhoneE164("+15551234567")).toBe(true);
  });

  it("rejects junk, bare rows, and stubs", () => {
    expect(isValidPhoneE164("")).toBe(false);
    expect(isValidPhoneE164("9876543210")).toBe(false); // legacy bare row
    expect(isValidPhoneE164("+913")).toBe(false); // too short
    expect(isValidPhoneE164("+01234567890")).toBe(false); // E.164 first digit 1-9
    expect(isValidPhoneE164("not-a-phone")).toBe(false);
    expect(isValidPhoneE164(null)).toBe(false);
  });
});

describe("samePhoneNumber", () => {
  it("matches E.164 against the legacy storage shapes", () => {
    expect(samePhoneNumber("+919876543210", "9876543210")).toBe(true);
    expect(samePhoneNumber("+919876543210", "09876543210")).toBe(true);
    expect(samePhoneNumber("+919876543210", "919876543210")).toBe(true);
    expect(samePhoneNumber("9876543210", "+91 98765 43210")).toBe(true);
    expect(samePhoneNumber("+15551234567", "+15551234567")).toBe(true);
  });

  it("never matches different numbers or blank values", () => {
    expect(samePhoneNumber("+919876543210", "+919876543211")).toBe(false);
    expect(samePhoneNumber("+15551234567", "+919876543210")).toBe(false);
    expect(samePhoneNumber("", "+919876543210")).toBe(false);
    expect(samePhoneNumber(null, undefined)).toBe(false);
  });
});

describe("displayPhone", () => {
  it("shows bare Indian national rows as +91 (the storage rule)", () => {
    expect(displayPhone("8606806956")).toBe("+918606806956");
  });

  it("passes E.164 and other values through untouched", () => {
    expect(displayPhone("+918606806956")).toBe("+918606806956");
    expect(displayPhone("+442071234567")).toBe("+442071234567");
    expect(displayPhone("")).toBe("");
    expect(displayPhone(null)).toBe("");
  });
});

describe("phoneDigits", () => {
  it("extracts digits from any human format", () => {
    expect(phoneDigits("+91 98765 43210")).toBe("919876543210");
    expect(phoneDigits("(555) 123-4567")).toBe("5551234567");
    expect(phoneDigits(null)).toBe("");
  });
});
