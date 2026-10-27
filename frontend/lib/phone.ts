/**
 * Phone helpers for the E.164 storage contract (issue #88).
 *
 * The backend normalizes every phone write to E.164 with an India-default
 * rule (apps/users/phone.py): unambiguous Indian numbers become
 * `+91XXXXXXXXXX`, other "+" numbers pass through, and ambiguous input is
 * left untouched rather than guessed. These helpers let the dashboard compose
 * that same shape at the source — the country selector picks the dial code,
 * the text field holds national digits — and keep display/lookup tolerant of
 * the legacy raw rows still out there during the migration rollout.
 */

import {
  DEFAULT_COUNTRY_ISO,
  PHONE_COUNTRIES,
  findCountryByIso,
  type PhoneCountry,
} from "./phoneCountries";

/** The digits inside a phone value; separators are stripped, never rejected. */
export function phoneDigits(raw: string | null | undefined): string {
  return String(raw ?? "").replace(/\D/g, "");
}

/**
 * Split a stored/typed value into a country and national digits.
 *
 * "+"-prefixed values match the longest known dial code; anything else
 * (legacy bare rows, partially typed numbers) lands on the platform default
 * country with the digits shown as-is, mirroring the backend's
 * India-default storage rule.
 */
export function parsePhoneInput(
  raw: string | null | undefined,
): { country: PhoneCountry; national: string } {
  const text = String(raw ?? "").trim();
  if (!text) return { country: findCountryByIso(DEFAULT_COUNTRY_ISO), national: "" };
  if (text.startsWith("+")) {
    const digits = text.slice(1).replace(/\D/g, "");
    // Longest dial match wins (e.g. 971 over 97 over 9).
    const match = PHONE_COUNTRIES.filter((c) => digits.startsWith(c.dial)).sort(
      (a, b) => b.dial.length - a.dial.length,
    )[0];
    if (match) return { country: match, national: digits.slice(match.dial.length) };
    // Unknown country: keep the default country selected and show the digits
    // so the value is never silently lost on edit.
    return { country: findCountryByIso(DEFAULT_COUNTRY_ISO), national: digits };
  }
  return {
    country: findCountryByIso(DEFAULT_COUNTRY_ISO),
    national: text.replace(/\D/g, ""),
  };
}

/** Compose the E.164 wire value from a dial code and national digits. */
export function formatPhoneE164(dial: string, national: string): string {
  const digits = national.replace(/\D/g, "");
  return digits ? `+${dial}${digits}` : "";
}

/** The E.164 wire shape: "+" + 1-15 digits, first digit 1-9 (ITU E.164). */
export function isValidPhoneE164(value: string | null | undefined): boolean {
  return /^\+[1-9]\d{6,14}$/.test(String(value ?? "").trim());
}

/**
 * Do two phone values denote the same number?
 *
 * Tolerant of the legacy storage shapes (bare national, trunk- and
 * country-code-prefixed without "+") the way the backend's
 * phone_lookup_candidates ladder is: a 10-digit national number matches any
 * value ending in those digits; anything else must match exactly.
 */
export function samePhoneNumber(a: string | null | undefined, b: string | null | undefined): boolean {
  // A leading 0 is a trunk prefix, never part of the E.164 number.
  const da = phoneDigits(a).replace(/^0+/, "");
  const db = phoneDigits(b).replace(/^0+/, "");
  if (!da || !db) return false;
  if (da === db) return true;
  const [short, long] = da.length <= db.length ? [da, db] : [db, da];
  return short.length === 10 && long.endsWith(short);
}

/**
 * Display form for a stored phone: bare Indian national rows read as
 * "+91…" (the backend's own storage rule), everything else shows as stored.
 */
export function displayPhone(raw: string | null | undefined): string {
  const text = String(raw ?? "").trim();
  if (/^[2-9]\d{9}$/.test(phoneDigits(text)) && !text.startsWith("+")) {
    return `+91${phoneDigits(text)}`;
  }
  return text;
}
