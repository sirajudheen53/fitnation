"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { Button, Card, CardBody, Input, Spinner } from "@/components/ui";
import {
  errorMessage,
  fetchCustomers,
  fetchPtRemaining,
  fetchTrainers,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { PtPackBadge, ptPackCopy } from "./PtPackBadge";
import type { Customer } from "@/types/customer";
import type { PtRemaining, SessionBookingPayload, Trainer } from "@/types/trainer";

const DURATIONS = [30, 45, 60, 90];

/** Friendly copy per machine-readable booking-conflict reason (issue #55). */
export function conflictCopy(reason: string | undefined, detail: string): string {
  switch (reason) {
    case "no_active_pt_membership":
      return "This member has no active PT membership. Sell a PT plan before booking sessions.";
    case "pt_membership_expired":
      return "This member's PT membership has expired — renew it before booking.";
    case "session_pack_exhausted":
      return "This member's session pack is exhausted. Renew the pack to book more sessions.";
    case "trainer_slot_conflict":
      return `That slot clashes with the trainer's schedule. ${detail}`.trim();
    default:
      return detail || "Session booking rejected.";
  }
}

interface BookSessionDialogProps {
  /** Preselected customer id (e.g. booked from a customer's profile). */
  initialCustomerId?: number;
  /** Trainers are branch-scoped to this branch when booking. */
  onSubmit: (payload: SessionBookingPayload) => Promise<void>;
  /** Notifies the parent when the selected customer changes (pack meter refresh). */
  onCustomerChange?: (customerId: number | null) => void;
  onClose: () => void;
}

/**
 * New PT booking dialog (issue #55): customer search, active-trainer select,
 * slot fields and the per-customer PT pack meter. Booking conflicts (409)
 * surface as clear, specific copy.
 */
export function BookSessionDialog({
  initialCustomerId,
  onSubmit,
  onCustomerChange,
  onClose,
}: BookSessionDialogProps) {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [customersError, setCustomersError] = useState<string | null>(null);
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [customerSearch, setCustomerSearch] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [trainerId, setTrainerId] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState("60");
  const [notes, setNotes] = useState("");
  /** Pack state tagged with the customer it belongs to, so a customer
   * switch never shows a stale meter while the next fetch is in flight. */
  const [pack, setPack] = useState<{ customerId: number; data: PtRemaining } | null>(
    null,
  );
  const [submitting, setSubmitting] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchCustomers(token)
      .then((res) => setCustomers(res.results))
      .catch((err) => setCustomersError(errorMessage(err)));
    fetchTrainers(token, { is_active: true })
      .then((list) => {
        setTrainers(list);
        setTrainerId((prev) => prev || String(list[0]?.id ?? ""));
      })
      .catch(() => setTrainers([]));
  }, []);

  // Pack meter follows the selected customer; hidden when the API is absent.
  const selectedCustomerId = customer?.id ?? null;
  useEffect(() => {
    onCustomerChange?.(selectedCustomerId);
    if (selectedCustomerId === null) return;
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    fetchPtRemaining(selectedCustomerId, token)
      .then((data) => {
        if (!cancelled) setPack({ customerId: selectedCustomerId, data });
      })
      .catch(() => {
        if (!cancelled) setPack(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCustomerId]);

  const packDisplay =
    selectedCustomerId !== null && pack?.customerId === selectedCustomerId
      ? pack.data
      : null;

  const filteredCustomers = useMemo(() => {
    const list = customers ?? [];
    const q = customerSearch.trim().toLowerCase();
    if (!q) return list.slice(0, 8);
    return list
      .filter((c) => `${c.name} ${c.email ?? ""} ${c.phone ?? ""}`.toLowerCase().includes(q))
      .slice(0, 8);
  }, [customers, customerSearch]);

  async function submit() {
    const token = getToken();
    if (!token || !customer || !trainerId) return;
    setSubmitting(true);
    setConflict(null);
    const scheduled = new Date(`${date}T${time}`);
    try {
      await onSubmit({
        trainer: Number(trainerId),
        customer: customer.id,
        branch: customer.branch,
        scheduled_at: scheduled.toISOString(),
        duration_minutes: Number(duration),
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch (err) {
      const data = (err as { data?: { reason?: string; detail?: string } }).data;
      setConflict(conflictCopy(data?.reason, errorMessage(err)));
      setSubmitting(false);
    }
  }

  const packBlocks = packDisplay !== null && !packDisplay.can_book;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Book PT session</h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          {conflict && (
            <p
              className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"
              data-testid="booking-conflict"
            >
              {conflict}
            </p>
          )}

          {customers === null && !customersError ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : customersError ? (
            <p className="text-sm text-red-600">{customersError}</p>
          ) : (
            <>
              <div className="space-y-2">
                <span className="block text-sm font-medium text-gray-700">Customer</span>
                {customer ? (
                  <div
                    className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm"
                    data-testid="selected-customer"
                  >
                    <span className="font-medium text-gray-900">{customer.name}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCustomer(null);
                        setCustomerSearch("");
                      }}
                      aria-label={`Change customer from ${customer.name}`}
                    >
                      Change
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="relative">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                      <input
                        type="search"
                        value={customerSearch}
                        onChange={(e) => setCustomerSearch(e.target.value)}
                        placeholder="Search customers…"
                        aria-label="Search customers"
                        className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                    <div className="max-h-40 space-y-1 overflow-y-auto" data-testid="customer-options">
                      {filteredCustomers.length === 0 ? (
                        <p className="py-4 text-center text-sm text-gray-500">
                          No customers match your search.
                        </p>
                      ) : (
                        filteredCustomers.map((c) => (
                          <button
                            key={c.id}
                            type="button"
                            onClick={() => setCustomer(c)}
                            className="block w-full rounded-lg border border-gray-200 px-3 py-2 text-left text-sm hover:bg-gray-50"
                          >
                            <span className="block font-medium text-gray-900">{c.name}</span>
                            <span className="block text-xs text-gray-500">
                              {c.email || c.phone || `#${c.id}`}
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>

              {customer && (
                <div className="space-y-1" data-testid="pack-meter">
                  {packDisplay ? (
                    <>
                      <PtPackBadge pack={packDisplay} />
                      {!packDisplay.can_book && (
                        <p className="text-xs text-amber-700">{ptPackCopy(packDisplay)}</p>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-gray-400">Checking PT pack…</p>
                  )}
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="session-trainer" className="block text-sm font-medium text-gray-700">
                  Trainer
                </label>
                <select
                  id="session-trainer"
                  value={trainerId}
                  onChange={(e) => setTrainerId(e.target.value)}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  {trainers.length === 0 && <option value="">No active trainers</option>}
                  {trainers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.first_name} {t.last_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Input label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                <Input label="Start time" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="session-duration" className="block text-sm font-medium text-gray-700">
                  Duration
                </label>
                <select
                  id="session-duration"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  {DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {d} minutes
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="session-notes" className="block text-sm font-medium text-gray-700">
                  Notes
                </label>
                <textarea
                  id="session-notes"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Focus areas, warm-up notes…"
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} disabled={submitting}>
                  Cancel
                </Button>
                <Button
                  onClick={submit}
                  disabled={!customer || !trainerId || packBlocks || submitting}
                  loading={submitting}
                  aria-label="Confirm booking"
                >
                  Book session
                </Button>
              </div>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
