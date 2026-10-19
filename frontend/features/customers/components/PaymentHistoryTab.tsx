"use client";

import Link from "next/link";
import { ArrowRight, CreditCard } from "lucide-react";
import { Card, CardHeader, CardBody, Button, Badge } from "@/components/ui";
import {
  formatPaymentDate,
  getPaymentMethodLabel,
  getPaymentKindLabel,
  getPaymentStatusLabel,
} from "@/features/payments/components/PaymentTable";
import type { Customer } from "@/types/customer";
import type { Payment, PaymentKind, PaymentStatus } from "@/types/payment";

/** Membership vs Admission label for a payment row (msg 2438). */
export function getPaymentKindBadgeVariant(
  kind: PaymentKind | undefined,
): "default" | "info" {
  return kind === "admission" ? "info" : "default";
}

const STATUS_VARIANTS: Record<PaymentStatus, "success" | "warning" | "danger" | "info"> = {
  completed: "success",
  pending: "warning",
  failed: "danger",
  refunded: "info",
};

interface PaymentHistoryTabProps {
  customer: Customer;
  /** The customer's payments (?customer=<id>); undefined while loading. */
  payments?: Payment[];
  loading?: boolean;
}

export function PaymentHistoryTab({
  customer,
  payments,
  loading = false,
}: PaymentHistoryTabProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900">Payment history</h3>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <CreditCard className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-gray-700">
                  View all payments, invoices and receipts for this customer.
                </p>
                <p className="text-xs text-gray-500">
                  Includes membership renewals, admission fees, marketplace orders and personal
                  training charges.
                </p>
              </div>
            </div>
            <Link href={`/payments?customer=${encodeURIComponent(customer.email ?? "")}`}>
              <Button size="sm">
                View payment history <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h3 className="text-base font-semibold text-gray-900">Recent payments</h3>
        </CardHeader>
        <CardBody>
          {loading ? (
            <p className="py-6 text-center text-sm text-gray-500">Loading payments…</p>
          ) : !payments || payments.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-500">
              No payments recorded for this customer yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-gray-100 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Date</th>
                    <th className="py-2 pr-4 font-medium">Kind</th>
                    <th className="py-2 pr-4 font-medium">Amount</th>
                    <th className="py-2 pr-4 font-medium">Method</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {payments.map((payment) => (
                    <tr key={payment.id}>
                      <td className="py-3 pr-4 text-gray-600">
                        {formatPaymentDate(payment.payment_date)}
                      </td>
                      <td className="py-3 pr-4">
                        <Badge variant={getPaymentKindBadgeVariant(payment.kind)}>
                          {getPaymentKindLabel(payment.kind)}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 font-medium text-gray-900">
                        ₹{Number(payment.amount).toLocaleString()}
                      </td>
                      <td className="py-3 pr-4 text-gray-600">
                        {getPaymentMethodLabel(payment.method)}
                      </td>
                      <td className="py-3">
                        <Badge variant={STATUS_VARIANTS[payment.status]}>
                          {getPaymentStatusLabel(payment.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
