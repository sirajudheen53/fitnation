"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_COUNTRY_ISO,
  PHONE_COUNTRIES,
  countryFlag,
  findCountryByIso,
} from "@/lib/phoneCountries";
import { formatPhoneE164, isAcceptablePhoneValue, parsePhoneInput, resolvePhoneE164 } from "@/lib/phone";

interface PhoneInputProps {
  label?: string;
  error?: string;
  hint?: string;
  /** Full phone value in E.164 ("+919876543210") or "" — legacy raw values parse too. */
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  id?: string;
  disabled?: boolean;
  required?: boolean;
  autoComplete?: string;
  /** Placeholder for the national-number field. */
  placeholder?: string;
}

const SELECT_CLASSES =
  "rounded-lg border border-gray-300 bg-white px-2 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500";

const INPUT_CLASSES =
  "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500";

/**
 * Phone field with a country-code selector (issue #88).
 *
 * Emits the E.164 shape the backend stores ("+<dial><national digits>", ""
 * when empty) so forms hold one string and the wire value is canonical from
 * the source. Paste of a full international number re-splits into country +
 * national instead of being mangled. Kept deliberately native-elements-only
 * — a select plus a text input, styled like the shared Input.
 *
 * Issue #99: while a value is present, a "Will save as …" line previews the
 * exact E.164 value the backend's storage rule will hold (mirrored in
 * resolvePhoneE164); once the field is blurred with a value that rule can't
 * normalize, the preview turns into an explicit red error. A form-supplied
 * `error` always wins so submit-time messages aren't duplicated.
 */
export function PhoneInput({
  label,
  error,
  hint,
  value,
  onChange,
  onBlur,
  id,
  disabled,
  required,
  autoComplete,
  placeholder = "98765 43210",
}: PhoneInputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-") || "phone";
  const initial = parsePhoneInput(value);
  const [countryIso, setCountryIso] = useState(initial.country.iso);
  const [national, setNational] = useState(initial.national);
  // The normalization state speaks only after the user leaves the field —
  // mid-typing an incomplete number is expected, not an error (#99).
  const [blurred, setBlurred] = useState(false);
  // Values the component itself emitted are echoed back through `value`;
  // anything else is an external reset (form prefill) and re-splits.
  const lastEmitted = useRef(value);

  useEffect(() => {
    if (value !== lastEmitted.current) {
      const next = parsePhoneInput(value);
      setCountryIso(next.country.iso);
      setNational(next.national);
      lastEmitted.current = value;
    }
  }, [value]);

  const country = findCountryByIso(countryIso);
  // The stored value the backend's rule will hold for the current form value —
  // canonical E.164 for everything the component emits, and the resolved
  // target for untouched legacy prefills (bare Indian rows).
  const resolved = resolvePhoneE164(value);
  const hasValue = value.trim() !== "";
  const unnormalizable = hasValue && !isAcceptablePhoneValue(resolved);

  const emit = (iso: string, digits: string) => {
    const next = formatPhoneE164(findCountryByIso(iso).dial, digits);
    lastEmitted.current = next;
    onChange(next);
  };

  const handleNationalChange = (raw: string) => {
    let iso = countryIso;
    let digits = raw.replace(/\D/g, "");
    if (raw.includes("+") || digits.length > country.maxDigits) {
      // A full international number pasted/typed into the national field:
      // re-split on the dial code (longest match) instead of truncating it.
      const reparsed = parsePhoneInput(`+${digits}`);
      iso = reparsed.country.iso;
      setCountryIso(iso);
      digits = reparsed.national;
    }
    if (digits.startsWith("0") && digits.length > country.maxDigits) {
      // Trunk prefix inside an overlong paste ("09876543210") — E.164 has none.
      digits = digits.slice(1);
    }
    digits = digits.slice(0, findCountryByIso(iso).maxDigits);
    setNational(digits);
    emit(iso, digits);
  };

  const handleCountryChange = (iso: string) => {
    // Keep the digits the user already typed — the dial code around them is
    // what the switch changes; silently trimming them would lose input.
    setCountryIso(iso);
    emit(iso, national);
  };

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <div className="flex gap-2">
        <select
          aria-label={label ? `${label} country code` : "Country code"}
          className={cn(
            SELECT_CLASSES,
            (error || (unnormalizable && blurred)) &&
              "border-red-500 focus:border-red-500 focus:ring-red-500",
          )}
          value={countryIso}
          disabled={disabled}
          onChange={(e) => handleCountryChange(e.target.value)}
        >
          <option value={DEFAULT_COUNTRY_ISO}>
            {countryFlag(DEFAULT_COUNTRY_ISO)} +{findCountryByIso(DEFAULT_COUNTRY_ISO).dial}
          </option>
          {PHONE_COUNTRIES.filter((c) => c.iso !== DEFAULT_COUNTRY_ISO).map((c) => (
            <option key={c.iso} value={c.iso}>
              {countryFlag(c.iso)} +{c.dial} · {c.name}
            </option>
          ))}
        </select>
        <input
          id={inputId}
          type="tel"
          inputMode="tel"
          className={cn(
            INPUT_CLASSES,
            (error || (unnormalizable && blurred)) &&
              "border-red-500 focus:border-red-500 focus:ring-red-500",
          )}
          value={national}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          autoComplete={autoComplete}
          aria-invalid={!!error || (unnormalizable && blurred)}
          aria-describedby={
            error || (unnormalizable && blurred)
              ? `${inputId}-error`
              : hint
                ? `${inputId}-hint`
                : undefined
          }
          onChange={(e) => handleNationalChange(e.target.value)}
          onBlur={() => {
            setBlurred(true);
            onBlur?.();
          }}
        />
      </div>
      {error ? (
        <p id={`${inputId}-error`} className="text-sm text-red-600">
          {error}
        </p>
      ) : unnormalizable && blurred ? (
        <p id={`${inputId}-error`} className="text-sm text-red-600" data-testid="phone-normalize-error">
          This number can&apos;t be saved as entered — check the country code and digits.
        </p>
      ) : (
        <>
          {hasValue && (
            <p className="text-sm text-gray-500" data-testid="phone-preview">
              Will save as <span className="font-medium text-gray-700">{resolved}</span>
            </p>
          )}
          {hint && (
            <p id={`${inputId}-hint`} className="text-sm text-gray-500">
              {hint}
            </p>
          )}
        </>
      )}
    </div>
  );
}
