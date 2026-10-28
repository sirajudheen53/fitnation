"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  CalendarDays,
  CalendarCheck,
  Activity,
  CheckCircle2,
  Hash,
  CreditCard,
  Receipt,
  MapPin,
  Target,
  Ruler,
  HeartPulse,
  Clock,
} from "lucide-react";
import { Card, CardHeader, CardBody, Badge, Button, Input } from "@/components/ui";
import { CustomerAvatar, getCustomerDisplayName } from "./CustomerAvatar";
import {
  formatPaymentDate,
  getPaymentMethodLabel,
  getPaymentStatusLabel,
} from "@/features/payments/components/PaymentTable";
import {
  STATUS_VARIANTS,
  formatMembershipDate,
  getMembershipStatusLabel,
} from "@/features/memberships/components/MembershipTable";
import { RenewMembershipDialog } from "@/features/memberships/components/RenewMembershipDialog";
import type { Customer } from "@/types/customer";
import type { Membership, MembershipPlan, MembershipStatus } from "@/types/membership";
import type { AttendanceListResponse } from "@/types/attendance";
import type { Payment, PaymentMethod } from "@/types/payment";
import type { ProgressSummary } from "@/types/customer-detail";

/** Same desk-collection methods as the create-form admission capture. */
const ADMISSION_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "upi", label: "UPI" },
  { value: "card", label: "Card" },
  { value: "other", label: "Other" },
];

/** Format a member-since date (YYYY-MM-DD or ISO) to a readable date. */
export function formatMemberSince(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Build a numeric stat from a string/number/null value. */
export function toNumber(value: string | number | null | undefined): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** First non-empty candidate formatted to 1 decimal, or the em dash placeholder. */
export function formatStatValue(
  ...candidates: (string | number | null | undefined)[]
): string {
  for (const value of candidates) {
    if (value !== null && value !== undefined && value !== "") {
      return Number(value).toFixed(1);
    }
  }
  return "—";
}

/**
 * "as of <date>" freshness caption for a stat value sourced from the latest
 * body measurement. Undefined when the candidate is empty (the value came
 * from health_profile or nothing at all) or the measurement has no usable
 * date — those cards stay caption-free.
 */
export function measurementAsOf(
  candidate: string | number | null | undefined,
  measurement: { date_logged: string } | null | undefined,
): string | undefined {
  if (candidate === null || candidate === undefined || candidate === "") {
    return undefined;
  }
  const formatted = formatMemberSince(measurement?.date_logged);
  return formatted === "—" ? undefined : `as of ${formatted}`;
}

/** Latest admission payment for the customer (newest created_at wins). */
export function latestAdmissionPayment(
  payments: Payment[] | undefined,
): Payment | null {
  if (!payments || payments.length === 0) return null;
  return [...payments].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  )[0];
}

/**
 * The membership that best represents the customer's current standing:
 * the active one with the latest end date, falling back through pending,
 * expired and cancelled in that order (latest end date within each rank).
 */
export function resolvePrimaryMembership(
  memberships: Membership[],
): Membership | null {
  if (memberships.length === 0) return null;
  const statusRank: Record<MembershipStatus, number> = {
    active: 0,
    pending: 1,
    expired: 2,
    cancelled: 3,
  };
  return [...memberships].sort(
    (a, b) =>
      statusRank[a.status] - statusRank[b.status] ||
      b.end_date.localeCompare(a.end_date),
  )[0];
}

/** Calendar days from `today` until the membership end date (negative when past). */
export function membershipDaysRemaining(
  endDate: string,
  today: Date = new Date(),
): number {
  const end = new Date(endDate);
  if (Number.isNaN(end.getTime())) return 0;
  // Compare UTC calendar dates so timezones can't shift the day boundary.
  const dayUtc = (d: Date) =>
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  return Math.round((dayUtc(end) - dayUtc(today)) / 86_400_000);
}

/**
 * Validity hint for a membership end date: "Expires in 12 days",
 * "Ends today", "Expired 3 days ago". Undefined when undated or unparseable.
 */
export function formatValidityHint(
  endDate: string | null | undefined,
  today: Date = new Date(),
): string | undefined {
  if (!endDate) return undefined;
  if (Number.isNaN(new Date(endDate).getTime())) return undefined;
  const days = membershipDaysRemaining(endDate, today);
  if (days > 1) return `Expires in ${days} days`;
  if (days === 1) return "Expires tomorrow";
  if (days === 0) return "Ends today";
  if (days === -1) return "Expired yesterday";
  return `Expired ${Math.abs(days)} days ago`;
}

/** Pending-payment totals shown as the membership dues line. */
export interface DuesSummary {
  total: number;
  count: number;
}

/** Sum the pending amounts and count the pending payments. */
export function summarizeDues(payments: Payment[]): DuesSummary {
  return {
    total: payments.reduce((sum, p) => sum + Number(p.amount || 0), 0),
    count: payments.length,
  };
}

/** Check-in stats for the profile attendance card (issue #93). */
export interface AttendanceSummaryStats {
  /** Total recorded visits (from the page envelope count — always exact). */
  totalVisits: number;
  /** Raw check-in timestamp of the most recent visit, null when none. */
  lastCheckIn: string | null;
  /** Visits dated in the calendar month of `today`. */
  thisMonth: number;
  /**
   * False when every record on the first page falls in the current month —
   * older same-month visits may exist beyond the page, so the UI shows "N+".
   */
  thisMonthExact: boolean;
}

/**
 * Derive check-in stats from the first page of the customer's attendance
 * (the backend orders records newest-first). `today` is injectable for tests.
 */
export function summarizeAttendance(
  page: { count: number; results: { date: string; check_in_time: string | null }[] },
  today: Date = new Date(),
): AttendanceSummaryStats {
  const monthPrefix = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const inMonth = page.results.filter((r) => r.date.startsWith(monthPrefix));
  const latest = page.results[0];
  return {
    totalVisits: page.count,
    lastCheckIn: latest ? (latest.check_in_time ?? latest.date) : null,
    thisMonth: inMonth.length,
    thisMonthExact: !(page.count > page.results.length && inMonth.length === page.results.length),
  };
}

/**
 * "15 Jan 2026 · 6:30 pm" for a check-in timestamp; date-only rendering for
 * plain YYYY-MM-DD dates; em dash when missing or unparseable.
 */
export function formatCheckIn(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const date = d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  if (iso.length <= 10) return date;
  return `${date} · ${d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}`;
}

export interface AdmissionFeeInput {
  amount: number;
  method: PaymentMethod;
}

interface OverviewTabProps {
  customer: Customer;
  summary?: ProgressSummary | null;
  /** Admission-kind payments for this customer (?kind=admission&customer=). */
  admissionPayments?: Payment[];
  /** True while the record-fee request is in flight. */
  recordingFee?: boolean;
  /**
   * Collect the admission fee — the caller decides whether to PATCH the
   * pending payment or POST a new one. Resolve true when recorded.
   */
  onRecordAdmissionFee?: (
    input: AdmissionFeeInput,
  ) => Promise<boolean>;
  /** This customer's memberships (null/undefined = not loaded → card hidden). */
  memberships?: Membership[] | null;
  /** Tenant plans, for the renewal duration preview in the confirm dialog. */
  membershipPlans?: MembershipPlan[];
  /**
   * Pending payments for this customer (?status=pending&customer=) — the
   * membership dues line. Undefined/null = not loaded → line omitted; an
   * empty array renders the "no pending dues" empty state.
   */
  pendingPayments?: Payment[] | null;
  /** Jump to the payment history tab from the dues line. */
  onViewPayments?: () => void;
  /**
   * First page of this customer's attendance (newest-first) for the
   * check-in summary. Undefined/null = not loaded → card hidden.
   */
  attendance?: AttendanceListResponse | null;
  /**
   * Renew a membership — the caller POSTs the renewal and updates its own
   * state. Resolves the updated membership (dialog closes) or null (stays
   * open). planId (issue #68) switches the plan before the extension.
   */
  onRenewMembership?: (
    membership: Membership,
    days?: number,
    planId?: number,
  ) => Promise<Membership | null>;
}

export function OverviewTab({
  customer,
  summary,
  admissionPayments,
  recordingFee = false,
  onRecordAdmissionFee,
  memberships,
  membershipPlans = [],
  pendingPayments,
  onViewPayments,
  attendance,
  onRenewMembership,
}: OverviewTabProps) {
  const profile = summary?.health_profile ?? null;
  const activeGoals = summary?.fitness_goals?.filter((g) => g.status === "active").length ?? 0;

  const latest = useMemo(() => latestAdmissionPayment(admissionPayments), [admissionPayments]);
  const [feeDialogOpen, setFeeDialogOpen] = useState(false);
  const [feeAmount, setFeeAmount] = useState("");
  const [feeMethod, setFeeMethod] = useState<PaymentMethod>("cash");
  const [feeError, setFeeError] = useState<string | null>(null);

  const [renewTarget, setRenewTarget] = useState<Membership | null>(null);
  const [renewing, setRenewing] = useState(false);

  const measurement = summary?.latest_measurement ?? null;
  const attendanceStats = attendance ? summarizeAttendance(attendance) : null;

  const stats: {
    label: string;
    value: string;
    icon: React.ReactNode;
    caption?: string;
  }[] = [
    {
      label: "Member since",
      value: formatMemberSince(customer.created_at),
      icon: <CalendarDays className="h-5 w-5" />,
    },
    {
      label: "BMI",
      value: formatStatValue(measurement?.bmi, profile?.bmi),
      caption: measurementAsOf(measurement?.bmi, measurement),
      icon: <Activity className="h-5 w-5" />,
    },
    {
      label: "Weight (kg)",
      value: formatStatValue(measurement?.weight_kg, profile?.weight_kg),
      caption: measurementAsOf(measurement?.weight_kg, measurement),
      icon: <Hash className="h-5 w-5" />,
    },
    {
      label: "Progress photos",
      value: summary ? String(summary.progress_photo_count) : "—",
      icon: <CheckCircle2 className="h-5 w-5" />,
    },
  ];

  const displayName = getCustomerDisplayName(customer);
  const hasAddress =
    customer.address_street || customer.address_city || customer.address_state || customer.address_postal_code;
  const addressLine2 = [customer.address_city, customer.address_state, customer.address_postal_code]
    .filter(Boolean)
    .join(", ");

  const openFeeDialog = () => {
    setFeeError(null);
    setFeeAmount(latest && latest.status === "pending" ? String(Number(latest.amount)) : "");
    setFeeDialogOpen(true);
  };

  const handleFeeConfirm = async () => {
    const amount = Number(feeAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setFeeError("Enter a valid amount");
      return;
    }
    const ok = await onRecordAdmissionFee?.({ amount, method: feeMethod });
    if (ok) setFeeDialogOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* Customer identity header */}
      <div className="flex items-center gap-4">
        <CustomerAvatar customer={customer} size="lg" />
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{displayName}</h3>
          <p className="text-sm text-gray-500">{customer.email || "No email on file"}</p>
        </div>
      </div>

      {/* Primary stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                {s.icon}
              </div>
              <div>
                <p className="text-lg font-semibold text-gray-900">{s.value}</p>
                <p className="text-xs text-gray-500">{s.label}</p>
                {s.caption && <p className="text-xs text-gray-400">{s.caption}</p>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick summary cards */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900">Quick summary</h3>
        </CardHeader>
        <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Account status</p>
            {customer.is_active ? (
              <Badge variant="success">Active</Badge>
            ) : (
              <Badge variant="danger">Inactive</Badge>
            )}
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Contact</p>
            <p className="text-sm text-gray-700">{customer.email || "No email on file"}</p>
            <p className="text-sm text-gray-500">{customer.phone || "No phone on file"}</p>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Address</p>
            {hasAddress ? (
              <div className="text-sm text-gray-700">
                {customer.address_street && <p>{customer.address_street}</p>}
                {addressLine2 && <p className="text-gray-500">{addressLine2}</p>}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No address on file</p>
            )}
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Emergency contact</p>
            <p className="text-sm text-gray-700">
              {customer.emergency_contact_name || "—"}
            </p>
            <p className="text-sm text-gray-500">{customer.emergency_contact_phone || "—"}</p>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Gender</p>
            <p className="text-sm capitalize text-gray-700">{customer.gender || "—"}</p>
          </div>
        </CardBody>
      </Card>

      {/* Admission fee (msg 2438) */}
      <Card>
        <CardHeader>
          <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
            <CreditCard className="h-5 w-5 text-brand-600" /> Admission fee
          </h3>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            {latest ? (
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                  <Receipt className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Badge variant={latest.status === "completed" ? "success" : "warning"}>
                      {latest.status === "completed" ? "Paid" : getPaymentStatusLabel(latest.status)}
                    </Badge>
                    <span className="text-sm font-semibold text-gray-900">
                      ₹{Number(latest.amount).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">
                    {getPaymentMethodLabel(latest.method)} · {formatPaymentDate(latest.payment_date)}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                  <Receipt className="h-5 w-5" aria-hidden="true" />
                </div>
                <p className="text-sm text-gray-500">No admission fee recorded yet.</p>
              </div>
            )}
            {onRecordAdmissionFee && (!latest || latest.status === "pending") && (
              <Button size="sm" onClick={openFeeDialog} disabled={recordingFee}>
                {latest && latest.status === "pending" ? "Record payment" : "Record admission fee"}
              </Button>
            )}
          </div>
        </CardBody>
      </Card>

      {/* Record/collect admission fee dialog */}
      {feeDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md" role="dialog" aria-modal="true">
            <CardBody className="space-y-4">
              <h3 className="text-base font-semibold text-gray-900">
                {latest && latest.status === "pending" ? "Record admission payment" : "Record admission fee"}
              </h3>
              <Input
                label="Amount (₹)"
                type="number"
                min="0"
                step="0.01"
                placeholder="1000"
                value={feeAmount}
                onChange={(e) => {
                  setFeeAmount(e.target.value);
                  setFeeError(null);
                }}
                error={feeError ?? undefined}
              />
              <div className="space-y-1.5">
                <label htmlFor="admission-fee-method" className="block text-sm font-medium text-gray-700">
                  Method
                </label>
                <select
                  id="admission-fee-method"
                  value={feeMethod}
                  onChange={(e) => setFeeMethod(e.target.value as PaymentMethod)}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  {ADMISSION_METHODS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setFeeDialogOpen(false)} disabled={recordingFee}>
                  Cancel
                </Button>
                <Button onClick={handleFeeConfirm} disabled={recordingFee}>
                  {recordingFee ? "Saving…" : "Save payment"}
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {/* Memberships + renewal + dues (issue #93) */}
      {memberships !== null && memberships !== undefined && (
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-gray-900">Memberships</h3>
          </CardHeader>
          <CardBody className="space-y-3">
            {memberships.length === 0 ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-gray-500">No memberships on file.</p>
                <Link href="/memberships/assign">
                  <Button size="sm" variant="outline">
                    Assign membership
                  </Button>
                </Link>
              </div>
            ) : (
              memberships.map((membership) => {
                const hint =
                  membership.status === "active" || membership.status === "expired"
                    ? formatValidityHint(membership.end_date)
                    : undefined;
                return (
                  <div
                    key={membership.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 p-4"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-gray-900">
                          {membership.plan_name}
                        </span>
                        <Badge variant={STATUS_VARIANTS[membership.status]}>
                          {getMembershipStatusLabel(membership.status)}
                        </Badge>
                        {hint && (
                          <span
                            className={
                              membership.status === "active" && membershipDaysRemaining(membership.end_date) <= 7
                                ? "text-xs font-medium text-amber-600"
                                : "text-xs text-gray-500"
                            }
                          >
                            {hint}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-gray-500">
                        {formatMembershipDate(membership.start_date)} –{" "}
                        {formatMembershipDate(membership.end_date)}
                        {membership.price != null &&
                          ` · ₹${Number(membership.price).toLocaleString()}`}
                      </p>
                    </div>
                    {(membership.status === "active" || membership.status === "expired") &&
                      onRenewMembership && (
                        <Button size="sm" variant="outline" onClick={() => setRenewTarget(membership)}>
                          Renew
                        </Button>
                      )}
                  </div>
                );
              })
            )}
            {pendingPayments !== null && pendingPayments !== undefined && (
              <div
                className={`flex items-center justify-between gap-3 rounded-xl border p-4 ${
                  pendingPayments.length > 0
                    ? "border-amber-200 bg-amber-50"
                    : "border-gray-200"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                      pendingPayments.length > 0
                        ? "bg-amber-100 text-amber-600"
                        : "bg-brand-50 text-brand-600"
                    }`}
                  >
                    <Receipt className="h-5 w-5" aria-hidden="true" />
                  </div>
                  {pendingPayments.length > 0 ? (
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        ₹{summarizeDues(pendingPayments).total.toLocaleString()} pending
                      </p>
                      <p className="text-xs text-gray-500">
                        {pendingPayments.length} pending payment
                        {pendingPayments.length > 1 ? "s" : ""}
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">No pending dues.</p>
                  )}
                </div>
                {pendingPayments.length > 0 && onViewPayments && (
                  <Button size="sm" variant="outline" onClick={onViewPayments}>
                    View payments
                  </Button>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Tab links */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Link
          href={`/customers/${customer.id}#goals`}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Target className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium text-gray-900">Fitness Goals</p>
            <p className="text-xs text-gray-500">
              {activeGoals > 0 ? `${activeGoals} active goal${activeGoals > 1 ? "s" : ""}` : "No goals yet"}
            </p>
          </div>
        </Link>

        <Link
          href={`/customers/${customer.id}#measurements`}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Ruler className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium text-gray-900">Body Measurements</p>
            <p className="text-xs text-gray-500">
              {summary?.latest_measurement
                ? `Last: ${formatMemberSince(summary.latest_measurement.date_logged)}`
                : "No measurements yet"}
            </p>
          </div>
        </Link>

        <Link
          href={`/customers/${customer.id}#health`}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <HeartPulse className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium text-gray-900">Health Profile</p>
            <p className="text-xs text-gray-500">
              {profile ? "On file" : "Not yet added"}
            </p>
          </div>
        </Link>
      </div>

      {/* Renewal confirmation */}
      {renewTarget && onRenewMembership && (
        <RenewMembershipDialog
          key={renewTarget.id}
          membership={renewTarget}
          plans={membershipPlans}
          busy={renewing}
          onConfirm={async (days, planId) => {
            setRenewing(true);
            const updated = await onRenewMembership(renewTarget, days, planId);
            setRenewing(false);
            if (updated) setRenewTarget(null);
          }}
          onClose={() => setRenewTarget(null)}
        />
      )}

      {/* Attendance / check-in summary (issue #93) */}
      {attendanceStats !== null && (
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-gray-900">Attendance</h3>
          </CardHeader>
          <CardBody>
            {attendanceStats.totalVisits === 0 ? (
              <p className="text-sm text-gray-500">No check-ins yet.</p>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                      <CalendarCheck className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {attendanceStats.totalVisits}
                      </p>
                      <p className="text-xs text-gray-500">Total visits</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                      <Activity className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {attendanceStats.thisMonth}
                        {attendanceStats.thisMonthExact ? "" : "+"}
                      </p>
                      <p className="text-xs text-gray-500">This month</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                      <Clock className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {formatCheckIn(attendanceStats.lastCheckIn)}
                      </p>
                      <p className="text-xs text-gray-500">Last check-in</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
