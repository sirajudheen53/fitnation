"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { DollarSign, Calendar, CreditCard, StickyNote } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Payment, PaymentFormData, PaymentMethod } from "@/types/payment";
import { errorMessage } from "@/lib/api";

const paymentSchema = z.object({
  customer_id: z.coerce.number().int().positive("Select a customer"),
  amount: z.coerce.number().positive("Amount must be greater than 0"),
  method: z.enum(["cash", "card", "upi", "bank_transfer", "other"]),
  membership_id: z.coerce.number().int().positive().optional().or(z.nan().transform(() => undefined)),
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Customer ID"
          type="number"
          min="1"
          placeholder="1"
          error={errors.customer_id?.message}
          {...register("customer_id")}
        />
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
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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

        <Input
          label="Payment date"
          type="date"
          icon={<Calendar className="h-4 w-4" />}
          error={errors.payment_date?.message}
          {...register("payment_date")}
        />
      </div>

      <Input
        label="Membership ID (optional)"
        type="number"
        min="1"
        placeholder="Link to a membership"
        error={errors.membership_id?.message}
        {...register("membership_id")}
      />

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
