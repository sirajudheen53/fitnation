"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  CalendarDays,
  User,
  Activity,
  CheckCircle2,
  Hash,
  CreditCard,
  Receipt,
  MapPin,
  Target,
  Ruler,
  HeartPulse,
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
import type { Membership, MembershipPlan } from "@/types/membership";
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
   * Renew a membership — the caller POSTs the renewal and updates its own
   * state. Resolves the updated membership (dialog closes) or null (stays open).
   */
  onRenewMembership?: (
    membership: Membership,
    days?: number,
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
            <p className="mb-2 text-sm font-medium text-gray-700">Membership status</p>
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

      {/* Memberships + renewal */}
      {memberships !== null && memberships !== undefined && (
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-gray-900">Memberships</h3>
          </CardHeader>
          <CardBody className="space-y-3">
            {memberships.length === 0 ? (
              <p className="text-sm text-gray-500">No memberships on file.</p>
            ) : (
              memberships.map((membership) => (
                <div
                  key={membership.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 p-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">
                        {membership.plan_name}
                      </span>
                      <Badge variant={STATUS_VARIANTS[membership.status]}>
                        {getMembershipStatusLabel(membership.status)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {formatMembershipDate(membership.start_date)} –{" "}
                      {formatMembershipDate(membership.end_date)}
                    </p>
                  </div>
                  {(membership.status === "active" || membership.status === "expired") &&
                    onRenewMembership && (
                      <Button size="sm" variant="outline" onClick={() => setRenewTarget(membership)}>
                        Renew
                      </Button>
                    )}
                </div>
              ))
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
          membership={renewTarget}
          plans={membershipPlans}
          busy={renewing}
          onConfirm={async (days) => {
            setRenewing(true);
            const updated = await onRenewMembership(renewTarget, days);
            setRenewing(false);
            if (updated) setRenewTarget(null);
          }}
          onClose={() => setRenewTarget(null)}
        />
      )}

      {/* Attendance */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900">Attendance</h3>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <User className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-gray-600">
                  Full attendance history and check-in streak are available from the Attendance
                  section.
                </p>
              </div>
            </div>
            <Link href={`/attendance?customer=${encodeURIComponent(customer.email ?? "")}`}>
              <Badge variant="info" className="cursor-pointer hover:bg-blue-100">
                View attendance →
              </Badge>
            </Link>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
