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

/** The bare Indian national number the backend's storage rule accepts. */
const IN_NATIONAL_RE = /^[2-9]\d{9}$/;

/** Trunk/country prefixes a bare Indian number is commonly typed with. */
const IN_PREFIXES = ["0", "91", "091"] as const;

/** Separators phone fields collect from copy-paste; stripped before shape checks. */
const PHONE_SEPARATORS_RE = /[\s().-]/g;

/** The 10-digit Indian national number inside `digits`, per apps/users/phone.py. */
function indianNationalDigits(digits: string): string | null {
  if (IN_NATIONAL_RE.test(digits)) return digits;
  for (const prefix of IN_PREFIXES) {
    if (digits.startsWith(prefix) && IN_NATIONAL_RE.test(digits.slice(prefix.length))) {
      return digits.slice(prefix.length);
    }
  }
  return null;
}

/**
 * What the backend's storage rule (apps/users/phone.py normalize_e164) turns
 * `raw` into — the source for the PhoneInput "will save as" preview (#99).
 * An unambiguous Indian number becomes `+91XXXXXXXXXX` (bare, 0/91/091-
 * prefixed, or +91-prefixed with separators); other "+" numbers pass through
 * with separators dropped; anything ambiguous is returned untouched rather
 * than guessed — exactly the backend's ambiguity stance, so the preview never
 * promises a normalization the API won't perform.
 */
export function resolvePhoneE164(raw: string | null | undefined): string {
  const text = String(raw ?? "").trim();
  if (!text) return "";
  const cleaned = text.replace(PHONE_SEPARATORS_RE, "");
  if (cleaned.startsWith("+")) {
    const digits = cleaned.slice(1);
    if (!digits) return text;
    const rest = digits.startsWith("91") ? digits.slice(2) : "";
    const national = rest ? indianNationalDigits(rest) : null;
    if (national !== null) return `+91${national}`;
    return cleaned;
  }
  const national = indianNationalDigits(phoneDigits(text));
  if (national !== null) return `+91${national}`;
  return text;
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
    const match = matchDialCode(digits);
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

/** Longest known dial code that prefixes `digits`, if any. */
export function matchDialCode(digits: string): PhoneCountry | null {
  return (
    PHONE_COUNTRIES.filter((c) => digits.startsWith(c.dial)).sort(
      (a, b) => b.dial.length - a.dial.length,
    )[0] ?? null
  );
}

/** Compose the E.164 wire value from a dial code and national digits. */
export function formatPhoneE164(dial: string, national: string): string {
  const digits = national.replace(/\D/g, "");
  return digits ? `+${dial}${digits}` : "";
}

/**
 * Canonical form-state value: compact E.164 for "+"-values with a known dial
 * code (e.g. "+91 98765 43210" → "+919876543210"), separators stripped
 * otherwise. Use on form prefill so an untouched legacy-format field still
 * submits a clean value; PhoneInput keeps everything canonical after edits.
 */
export function normalizePhoneValue(raw: string | null | undefined): string {
  const text = String(raw ?? "").trim();
  if (!text) return "";
  if (text.startsWith("+")) {
    const digits = text.slice(1).replace(/\D/g, "");
    const match = matchDialCode(digits);
    return match ? `+${match.dial}${digits.slice(match.dial.length)}` : `+${digits}`;
  }
  return text.replace(/\D/g, "");
}

/** The E.164 wire shape: "+" + 1-15 digits, first digit 1-9 (ITU E.164). */
export function isValidPhoneE164(value: string | null | undefined): boolean {
  return /^\+[1-9]\d{6,14}$/.test(String(value ?? "").trim());
}

/**
 * Schema-level acceptance: canonical E.164, or the legacy bare Indian row
 * shape the backend's save-time rule still normalizes (the #88 transition —
 * the frontend must not be stricter than the API it talks to).
 */
export function isAcceptablePhoneValue(value: string | null | undefined): boolean {
  const text = String(value ?? "").trim();
  if (!text) return false;
  return isValidPhoneE164(text) || /^[2-9]\d{9}$/.test(text);
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
