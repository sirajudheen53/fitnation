/**
 * Country codes for the PhoneInput selector (issue #88).
 *
 * The platform's home market is India (the backend's phone rule is
 * India-default), so India is first and is the default selection. The list
 * is a curated set of common countries rather than the full ITU table —
 * numbers for countries outside it can still be entered by typing the full
 * E.164 form, which the backend stores verbatim.
 *
 * `maxDigits` caps typing with the country's longest national significant
 * number; validation itself is the generic E.164 shape (lib/phone.ts).
 */
export interface PhoneCountry {
  /** ISO 3166-1 alpha-2 code (also the <option> value). */
  iso: string;
  name: string;
  /** Dial code, digits only (no "+"). */
  dial: string;
  /** Longest national significant number, for the typing cap. */
  maxDigits: number;
}

export const DEFAULT_COUNTRY_ISO = "IN";

export const PHONE_COUNTRIES: PhoneCountry[] = [
  { iso: "IN", name: "India", dial: "91", maxDigits: 10 },
  { iso: "AE", name: "United Arab Emirates", dial: "971", maxDigits: 9 },
  { iso: "AU", name: "Australia", dial: "61", maxDigits: 9 },
  { iso: "BD", name: "Bangladesh", dial: "880", maxDigits: 10 },
  { iso: "BH", name: "Bahrain", dial: "973", maxDigits: 8 },
  { iso: "BR", name: "Brazil", dial: "55", maxDigits: 11 },
  { iso: "CA", name: "Canada", dial: "1", maxDigits: 10 },
  { iso: "CH", name: "Switzerland", dial: "41", maxDigits: 9 },
  { iso: "CN", name: "China", dial: "86", maxDigits: 11 },
  { iso: "DE", name: "Germany", dial: "49", maxDigits: 11 },
  { iso: "ES", name: "Spain", dial: "34", maxDigits: 9 },
  { iso: "FR", name: "France", dial: "33", maxDigits: 9 },
  { iso: "GB", name: "United Kingdom", dial: "44", maxDigits: 10 },
  { iso: "GH", name: "Ghana", dial: "233", maxDigits: 9 },
  { iso: "HK", name: "Hong Kong", dial: "852", maxDigits: 8 },
  { iso: "ID", name: "Indonesia", dial: "62", maxDigits: 12 },
  { iso: "IE", name: "Ireland", dial: "353", maxDigits: 9 },
  { iso: "IL", name: "Israel", dial: "972", maxDigits: 9 },
  { iso: "IT", name: "Italy", dial: "39", maxDigits: 11 },
  { iso: "JP", name: "Japan", dial: "81", maxDigits: 10 },
  { iso: "KE", name: "Kenya", dial: "254", maxDigits: 9 },
  { iso: "KR", name: "South Korea", dial: "82", maxDigits: 10 },
  { iso: "KW", name: "Kuwait", dial: "965", maxDigits: 8 },
  { iso: "LK", name: "Sri Lanka", dial: "94", maxDigits: 9 },
  { iso: "MV", name: "Maldives", dial: "960", maxDigits: 7 },
  { iso: "MX", name: "Mexico", dial: "52", maxDigits: 10 },
  { iso: "MY", name: "Malaysia", dial: "60", maxDigits: 10 },
  { iso: "NG", name: "Nigeria", dial: "234", maxDigits: 10 },
  { iso: "NL", name: "Netherlands", dial: "31", maxDigits: 9 },
  { iso: "NP", name: "Nepal", dial: "977", maxDigits: 10 },
  { iso: "NZ", name: "New Zealand", dial: "64", maxDigits: 10 },
  { iso: "OM", name: "Oman", dial: "968", maxDigits: 8 },
  { iso: "PH", name: "Philippines", dial: "63", maxDigits: 10 },
  { iso: "PK", name: "Pakistan", dial: "92", maxDigits: 10 },
  { iso: "PL", name: "Poland", dial: "48", maxDigits: 9 },
  { iso: "PT", name: "Portugal", dial: "351", maxDigits: 9 },
  { iso: "QA", name: "Qatar", dial: "974", maxDigits: 8 },
  { iso: "RU", name: "Russia", dial: "7", maxDigits: 10 },
  { iso: "SA", name: "Saudi Arabia", dial: "966", maxDigits: 9 },
  { iso: "SG", name: "Singapore", dial: "65", maxDigits: 8 },
  { iso: "TH", name: "Thailand", dial: "66", maxDigits: 9 },
  { iso: "TR", name: "Turkey", dial: "90", maxDigits: 10 },
  { iso: "US", name: "United States", dial: "1", maxDigits: 10 },
  { iso: "VN", name: "Vietnam", dial: "84", maxDigits: 10 },
  { iso: "ZA", name: "South Africa", dial: "27", maxDigits: 9 },
];

export function findCountryByIso(iso: string): PhoneCountry {
  return (
    PHONE_COUNTRIES.find((c) => c.iso === iso) ??
    // Unknown ISO (shouldn't happen — options come from this list) falls
    // back to the platform default rather than rendering a broken selector.
    PHONE_COUNTRIES[0]
  );
}

/** ISO code → flag emoji (regional indicator symbols), computed not stored. */
export function countryFlag(iso: string): string {
  if (!/^[A-Z]{2}$/.test(iso)) return "🏳️";
  return String.fromCodePoint(
    ...[...iso].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65),
  );
}
