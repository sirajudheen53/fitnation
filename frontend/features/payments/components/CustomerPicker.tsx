"use client";

/**
 * Searchable customer picker for the record-payment form (#103).
 *
 * Type-to-search by name/phone through the same `searchCustomers` lookup the
 * onboarding wizard uses, debounced so a fast typist costs one request per
 * settled query. The picker owns the search UX (loading/empty/error states);
 * the parent owns the picked customer and reacts to `onSelect`.
 */

import { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2, RotateCw, Search, X } from "lucide-react";
import { searchCustomers } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Customer } from "@/types/customer";

/** Below this many characters the search stays idle (avoids noisy 1-char scans). */
const MIN_QUERY_LENGTH = 2;
const DEFAULT_DEBOUNCE_MS = 300;

type SearchStatus = "idle" | "loading" | "done" | "error";

interface CustomerPickerProps {
  label?: string;
  /** The picked customer, or null when nothing is selected. */
  selected: Customer | null;
  /** Called with the picked customer on selection, and null on clear/reset. */
  onSelect: (customer: Customer | null) => void;
  /** Form-level validation message shown under the input. */
  error?: string;
  disabled?: boolean;
  placeholder?: string;
  /** Debounce window in ms; injectable for tests. */
  debounceMs?: number;
}

export function CustomerPicker({
  label = "Customer",
  selected,
  onSelect,
  error,
  disabled = false,
  placeholder = "Search by name or phone",
  debounceMs = DEFAULT_DEBOUNCE_MS,
}: CustomerPickerProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [open, setOpen] = useState(false);
  /** Bumped by the retry button so the effect re-runs without touching query. */
  const [retryTick, setRetryTick] = useState(0);
  /** Ignore stale responses after a newer keystroke, selection, or clear. */
  const requestSeq = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) return undefined;
    const token = getToken();
    if (!token) return undefined;
    const authToken: string = token;
    const seq = ++requestSeq.current;
    const timer = setTimeout(() => {
      searchCustomers(authToken, trimmed)
        .then((matches) => {
          if (seq !== requestSeq.current) return;
          setResults(matches);
          setStatus("done");
        })
        .catch(() => {
          if (seq !== requestSeq.current) return;
          setStatus("error");
        });
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [query, debounceMs, retryTick]);

  const handleQueryChange = (value: string) => {
    setQuery(value);
    // Editing the text drops the previous pick — the id must always come
    // from an explicit selection, never a half-typed name.
    if (selected) onSelect(null);
    const trimmed = value.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      requestSeq.current += 1; // invalidate any in-flight search
      setResults([]);
      setStatus("idle");
      setOpen(false);
    } else {
      setStatus("loading");
      setOpen(true);
    }
  };

  const pick = (customer: Customer) => {
    onSelect(customer);
    setQuery(customer.name);
    setResults([]);
    setStatus("idle");
    setOpen(false);
  };

  const clear = () => {
    requestSeq.current += 1;
    if (selected) onSelect(null);
    setQuery("");
    setResults([]);
    setStatus("idle");
    setOpen(false);
  };

  const retry = () => {
    setStatus("loading");
    setRetryTick((tick) => tick + 1);
  };

  const dropdownOpen =
    open && !disabled && (status === "loading" || status === "done" || status === "error");

  return (
    <div
      className="relative space-y-1.5"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      {label && (
        <label htmlFor="customer-picker-input" className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          id="customer-picker-input"
          type="text"
          role="combobox"
          aria-expanded={dropdownOpen}
          aria-controls="customer-picker-listbox"
          aria-autocomplete="list"
          aria-invalid={!!error}
          aria-describedby={error ? "customer-picker-error" : undefined}
          autoComplete="off"
          disabled={disabled}
          value={query}
          placeholder={placeholder}
          onChange={(e) => handleQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setOpen(false);
            } else if (e.key === "Enter" && dropdownOpen && status === "done" && results.length > 0) {
              // Enter picks the top match instead of submitting the form.
              e.preventDefault();
              pick(results[0]);
            }
          }}
          className={
            "block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-10 text-sm text-gray-900 " +
            "placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 " +
            (error ? "border-red-500 focus:border-red-500 focus:ring-red-500 " : "")
          }
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2">
          {status === "loading" ? (
            <Loader2 data-testid="customer-picker-spinner" className="h-4 w-4 animate-spin text-gray-400" />
          ) : query || selected ? (
            <button
              type="button"
              aria-label="Clear customer"
              onClick={clear}
              className="rounded p-1 text-gray-400 hover:text-gray-600"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      </div>
      {error && (
        <p id="customer-picker-error" className="text-sm text-red-600">
          {error}
        </p>
      )}

      {dropdownOpen && (
        <div
          id="customer-picker-listbox"
          role="listbox"
          aria-label="Customer search results"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg"
        >
          {status === "loading" && (
            <p data-testid="customer-picker-loading" className="px-3 py-2 text-sm text-gray-500">
              Searching customers…
            </p>
          )}
          {status === "error" && (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-red-600">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>Customer search failed.</span>
              <button
                type="button"
                onClick={retry}
                className="ml-auto inline-flex items-center gap-1 rounded px-2 py-1 text-brand-600 hover:bg-brand-50"
              >
                <RotateCw className="h-3.5 w-3.5" /> Retry
              </button>
            </div>
          )}
          {status === "done" &&
            results.map((customer) => (
              <button
                key={customer.id}
                type="button"
                role="option"
                aria-selected={selected?.id === customer.id}
                onClick={() => pick(customer)}
                className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-brand-50"
              >
                <span className="font-medium text-gray-900">{customer.name}</span>
                <span className="text-gray-500">{customer.phone ?? "No phone"}</span>
              </button>
            ))}
          {status === "done" && results.length === 0 && (
            <p data-testid="customer-picker-empty" className="px-3 py-2 text-sm text-gray-500">
              No customers match “{query.trim()}”.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
