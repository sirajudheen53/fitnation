"use client";

import Link from "next/link";
import { Eye } from "lucide-react";
import { Badge } from "@/components/ui";
import type { Payment, PaymentStatus } from "@/types/payment";

const STATUS_VARIANTS: Record<PaymentStatus, "success" | "warning" | "danger" | "info"> = {
  completed: "success",
  pending: "warning",
  failed: "danger",
  refunded: "info",
};

export function getPaymentStatusLabel(status: PaymentStatus): string {
  const labels: Record<PaymentStatus, string> = {
    completed: "Completed",
    pending: "Pending",
    failed: "Failed",
    refunded: "Refunded",
  };
  return labels[status];
}

export function getPaymentMethodLabel(method: Payment["method"]): string {
  const labels: Record<Payment["method"], string> = {
    cash: "Cash",
    card: "Card",
    upi: "UPI",
    bank_transfer: "Bank transfer",
    other: "Other",
  };
  return labels[method];
}

export function formatPaymentDate(date: string | null): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString();
}

export interface PaymentFilters {
  customer?: string;
  status?: PaymentStatus | "";
  from?: string;
  to?: string;
}

interface PaymentTableProps {
  payments: Payment[];
  filters: PaymentFilters;
  onFilterChange: (filters: PaymentFilters) => void;
  loading?: boolean;
}

export function PaymentTable({
  payments,
  filters,
  onFilterChange,
  loading = false,
}: PaymentTableProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-500">
        Loading payments…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="grid grid-cols-1 gap-3 rounded-xl border border-gray-200 bg-white p-4 md:grid-cols-4">
        <input
          type="text"
          placeholder="Filter by customer"
          value={filters.customer ?? ""}
          onChange={(e) => onFilterChange({ ...filters, customer: e.target.value })}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <select
          value={filters.status ?? ""}
          onChange={(e) =>
            onFilterChange({ ...filters, status: e.target.value as PaymentStatus | "" })
          }
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">All statuses</option>
          <option value="completed">Completed</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
          <option value="refunded">Refunded</option>
        </select>
        <input
          type="date"
          value={filters.from ?? ""}
          onChange={(e) => onFilterChange({ ...filters, from: e.target.value })}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <input
          type="date"
          value={filters.to ?? ""}
          onChange={(e) => onFilterChange({ ...filters, to: e.target.value })}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      {payments.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No payments match your filters.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-6 py-3 font-medium">Customer</th>
                <th className="px-6 py-3 font-medium">Amount</th>
                <th className="px-6 py-3 font-medium">Method</th>
                <th className="px-6 py-3 font-medium">Date</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {payments.map((payment) => (
                <tr key={payment.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">
                    {payment.customer_name}
                  </td>
                  <td className="px-6 py-4 text-gray-700">
                    ₹{Number(payment.amount).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {getPaymentMethodLabel(payment.method)}
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {formatPaymentDate(payment.payment_date)}
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={STATUS_VARIANTS[payment.status]}>
                      {getPaymentStatusLabel(payment.status)}
                    </Badge>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/payments/${payment.id}`}
                        className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                        aria-label="View payment"
                      >
                        <Eye className="h-4 w-4" />
                      </Link>
                    </div>
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
