"use client";

import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Calendar, CreditCard, DollarSign, StickyNote } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import { CustomerPicker } from "./CustomerPicker";
import type { Payment, PaymentFormData, PaymentMethod } from "@/types/payment";
import type { Membership } from "@/types/membership";
import type { Customer as CustomerRecord } from "@/types/customer";
import { errorMessage, fetchMemberships, fetchPayments } from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Empty text/NaN/undefined all mean "no membership chosen" — without this,
 * a cleared field coerces "" to 0 and submits a bogus positive() error.
 */
const emptyToUndefined = (value: unknown) =>
  value === "" || value === null || value === undefined ||
  (typeof value === "number" && Number.isNaN(value))
    ? undefined
    : value;

const paymentSchema = z.object({
  customer_id: z.preprocess(
    (v) =>
      v === "" || v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))
        ? 0
        : v,
    z.coerce.number().int().positive("Select a customer"),
  ),
  amount: z.coerce.number().positive("Amount must be greater than 0"),
  method: z.enum(["cash", "card", "upi", "bank_transfer", "other"]),
  membership_id: z.preprocess(emptyToUndefined, z.coerce.number().int().positive().optional()),
  notes: z.string().max(500).optional().or(z.literal("")),
  payment_date: z.string().min(1, "Payment date is required"),
});

type PaymentSchemaData = z.infer<typeof paymentSchema>;

const METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: "Cash",
  card: "Card",
  upi: "UPI",
  bank_transfer: "Bank transfer",
  other: "Other",
};

/**
 * The customer's membership this payment should default to (#103): their
 * active membership, else their latest one. The backend orders memberships
 * newest-first (-created_at) and has no per-customer filter, so callers pass
 * the already-filtered list.
 */
export function pickLatestMembership(
  memberships: Membership[],
  customerId: number,
): Membership | null {
  const mine = memberships.filter((m) => m.customer_id === customerId);
  return mine.find((m) => m.status === "active") ?? mine[0] ?? null;
}

/** Pending-payment totals surfaced next to the auto-linked membership. */
export interface MembershipLink {
  membership: Membership | null;
  pendingTotal: number;
  pendingCount: number;
}

export function summarizePending(payments: Payment[]): { total: number; count: number } {
  return {
    total: payments.reduce((sum, p) => sum + Number(p.amount || 0), 0),
    count: payments.length,
  };
}

interface PaymentFormProps {
  payment?: Payment;
  defaultValues?: Partial<PaymentFormData>;
  submitLabel?: string;
  onSubmit: (data: PaymentFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function PaymentForm({
  payment,
  defaultValues,
  submitLabel = "Record payment",
  onSubmit,
  error,
  loading = false,
}: PaymentFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<PaymentSchemaData>({
    resolver: zodResolver(paymentSchema),
    defaultValues: {
      customer_id: undefined,
      amount: 0,
      method: "cash",
      membership_id: undefined,
      notes: "",
      payment_date: new Date().toISOString().slice(0, 10),
      ...defaultValues,
    },
  });

  const [selectedCustomer, setSelectedCustomer] = useState<CustomerRecord | null>(null);
  const [link, setLink] = useState<MembershipLink | null>(null);
  const [linkLoading, setLinkLoading] = useState(false);
  /** Ignore stale link loads when the picked customer changes quickly. */
  const linkSeq = useRef(0);

  useEffect(() => {
    if (payment) {
      reset({
        customer_id: payment.customer_id,
        amount: Number(payment.amount) || 0,
        method: payment.method,
        membership_id: payment.membership_id ?? undefined,
        notes: payment.notes || "",
        payment_date: payment.payment_date.slice(0, 10),
      });
    }
  }, [payment, reset]);

  /**
   * Load the picked customer's memberships + pending payments and auto-fill
   * the membership field (#103). Both fetches are non-fatal: a failed
   * membership lookup leaves the field empty and editable.
   */
  const loadMembershipLink = (customerId: number) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setLinkLoading(true);
    const seq = ++linkSeq.current;
    Promise.all([
      fetchMemberships(authToken).catch(() => null),
      fetchPayments(authToken, { customer: customerId, status: "pending" }).catch(() => null),
    ]).then(([membershipRes, pendingRes]) => {
      if (seq !== linkSeq.current) return;
      const memberships = membershipRes ? membershipRes.results : [];
      const active = pickLatestMembership(memberships, customerId);
      const pending = pendingRes ? pendingRes.results : [];
      const pendingSummary = summarizePending(pending);
      setLink({
        membership: active,
        pendingTotal: pendingSummary.total,
        pendingCount: pendingSummary.count,
      });
      setLinkLoading(false);
      if (active) {
        setValue("membership_id", active.id, { shouldValidate: true, shouldDirty: true });
      }
    });
  };

  const handleCustomerSelect = (customer: CustomerRecord | null) => {
    setSelectedCustomer(customer);
    linkSeq.current += 1;
    setLink(null);
    setLinkLoading(false);
    if (customer) {
      setValue("customer_id", customer.id, { shouldValidate: true, shouldDirty: true });
      loadMembershipLink(customer.id);
    } else {
      // Validated immediately: an emptied required field says so right away.
      setValue("customer_id", 0, { shouldValidate: true, shouldDirty: true });
      setValue("membership_id", "");
    }
  };

  const handleFormSubmit = async (data: PaymentSchemaData) => {
    const payload: PaymentFormData = {
      customer_id: data.customer_id,
      amount: data.amount,
      method: data.method,
      membership_id:
        data.membership_id !== undefined && !Number.isNaN(data.membership_id)
          ? data.membership_id
          : undefined,
      notes: data.notes || undefined,
      payment_date: data.payment_date,
    };
    await onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      {/* customer_id is set via setValue from the picker; the hidden input
          keeps the field registered so shouldValidate/trigger work. */}
      <input type="hidden" {...register("customer_id")} />

      <CustomerPicker
        label="Customer"
        selected={selectedCustomer}
        onSelect={handleCustomerSelect}
        error={errors.customer_id?.message}
      />

      {linkLoading && (
        <p data-testid="membership-link-loading" className="text-sm text-gray-500">
          Checking memberships…
        </p>
      )}
      {link && (
        <div
          data-testid="membership-link"
          className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm"
        >
          {link.membership ? (
            <p className="text-gray-700">
              Auto-linked membership #{link.membership.id} ·{" "}
              <span className="font-medium">{link.membership.plan_name}</span> ·{" "}
              <span className="capitalize">{link.membership.status}</span>
            </p>
          ) : (
            <p className="text-gray-500">No membership found for this customer.</p>
          )}
          {link.pendingCount > 0 ? (
            <p className="mt-1 text-amber-700">
              Pending dues: ₹{link.pendingTotal.toFixed(2)} across {link.pendingCount}{" "}
              {link.pendingCount === 1 ? "payment" : "payments"}
            </p>
          ) : (
            <p className="mt-1 text-gray-500">No pending dues.</p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Amount"
          type="number"
          step="0.01"
          min="0"
          placeholder="1999"
          icon={<DollarSign className="h-4 w-4" />}
          error={errors.amount?.message}
          {...register("amount")}
        />
        <div className="space-y-1.5">
          <label htmlFor="method" className="block text-sm font-medium text-gray-700">
            Payment method
          </label>
          <div className="relative">
            <CreditCard className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <select
              id="method"
              {...register("method")}
              className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {(Object.keys(METHOD_LABELS) as PaymentMethod[]).map((m) => (
                <option key={m} value={m}>
                  {METHOD_LABELS[m]}
                </option>
              ))}
            </select>
          </div>
          {errors.method?.message && (
            <p className="text-sm text-red-600">{errors.method.message}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Payment date"
          type="date"
          icon={<Calendar className="h-4 w-4" />}
          error={errors.payment_date?.message}
          {...register("payment_date")}
        />
        <Input
          label="Membership ID"
          type="number"
          min="1"
          placeholder="Link to a membership"
          hint={
            link?.membership
              ? "Auto-filled from the customer's membership — edit if needed"
              : undefined
          }
          error={errors.membership_id?.message}
          {...register("membership_id")}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="notes" className="block text-sm font-medium text-gray-700">
          Notes
        </label>
        <div className="relative">
          <StickyNote className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-gray-400" />
          <textarea
            id="notes"
            rows={3}
            placeholder="Optional notes about this payment"
            {...register("notes")}
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        {errors.notes?.message && (
          <p className="text-sm text-red-600">{errors.notes.message}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
