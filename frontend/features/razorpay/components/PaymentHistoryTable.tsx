"use client";

import { useRouter } from "next/navigation";
import { Receipt } from "lucide-react";
import { Alert, Spinner } from "@/components/ui";
import type { RazorpayPayment, RazorpayPaymentStatus } from "@/types/razorpay";
import {
  formatRazorpayDate,
  getRazorpayMethodLabel,
  RazorpayStatusBadge,
} from "./RazorpayStatusBadge";

const STATUS_FILTERS: Array<{ value: RazorpayPaymentStatus | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "completed", label: "Paid" },
  { value: "failed", label: "Failed" },
  { value: "refunded", label: "Refunded" },
];

interface PaymentHistoryTableProps {
  payments: RazorpayPayment[];
  loading?: boolean;
  error?: unknown;
  status: RazorpayPaymentStatus | "all";
  onStatusChange: (status: RazorpayPaymentStatus | "all") => void;
  onRefresh?: () => void;
}

export function PaymentHistoryTable({
  payments,
  loading = false,
  error,
  status,
  onStatusChange,
  onRefresh,
}: PaymentHistoryTableProps) {
  const router = useRouter();

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map((filter) => {
            const active = status === filter.value;
            return (
              <button
                key={filter.value}
                onClick={() => onStatusChange(filter.value)}
                className={
                  active
                    ? "rounded-full bg-brand-600 px-3 py-1.5 text-xs font-medium text-white"
                    : "rounded-full border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                }
              >
                {filter.label}
              </button>
            );
          })}
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            Refresh
          </button>
        )}
      </div>

      {error ? (
        <Alert variant="error">{error instanceof Error ? error.message : "Failed to load payments."}</Alert>
      ) : loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-8 w-8" />
        </div>
      ) : payments.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-white py-16 text-center">
          <Receipt className="h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm font-medium text-gray-900">No payments found</p>
          <p className="mt-1 text-sm text-gray-500">Payments made via Razorpay will appear here.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Payment
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Customer
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Amount
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Method
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {payments.map((payment) => (
                <tr
                  key={payment.id}
                  className="cursor-pointer hover:bg-gray-50"
                  onClick={() => router.push(`/payments/razorpay/${payment.id}`)}
                >
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    #{payment.id}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    Customer #{payment.customer}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-semibold text-gray-900">
                    ₹{Number(payment.amount).toLocaleString("en-IN")}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm capitalize text-gray-700">
                    {getRazorpayMethodLabel(payment.payment_method)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">
                    <RazorpayStatusBadge status={payment.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatRazorpayDate(payment.paid_at ?? payment.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
