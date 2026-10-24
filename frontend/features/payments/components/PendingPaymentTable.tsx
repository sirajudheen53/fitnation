"use client";

import { Send } from "lucide-react";
import { Badge, Button } from "@/components/ui";
import { getPaymentStatusLabel, STATUS_VARIANTS } from "@/features/payments/components/PaymentTable";
import type { Payment } from "@/types/payment";

/**
 * Days a payment has been pending, counted from when it was created (issue #72).
 * Frontend copy convention: "today" for <1 day, otherwise the whole days.
 */
export function getPendingDays(payment: Pick<Payment, "created_at">, now: Date = new Date()): number {
  const created = new Date(payment.created_at).getTime();
  if (Number.isNaN(created)) return 0;
  return Math.max(0, Math.floor((now.getTime() - created) / 86_400_000));
}

/** Plan reference when the payment links a membership, else the invoice ref. */
export function getPendingPaymentRef(payment: Payment): string {
  if (payment.plan_name) return payment.plan_name;
  if (payment.invoice_id) return `Invoice #${payment.invoice_id}`;
  return "—";
}

interface PendingPaymentTableProps {
  payments: Payment[];
  sendingPaymentId: number | null;
  onSend: (payment: Payment) => void;
  /** Hidden without ``payments.record_payment`` (mirrors the route guard). */
  canSend?: boolean;
}

/**
 * Pending-payments queue (issue #72): unpaid charges with a "Send payment
 * link" action that pushes a Razorpay link over WhatsApp.
 */
export function PendingPaymentTable({
  payments,
  sendingPaymentId,
  onSend,
  canSend = true,
}: PendingPaymentTableProps) {
  if (payments.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
        <p className="text-sm text-gray-500">No pending payments — every charge is collected. 🎉</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-6 py-3 font-medium">Member</th>
            <th className="px-6 py-3 font-medium">Phone</th>
            <th className="px-6 py-3 font-medium">Amount</th>
            <th className="px-6 py-3 font-medium">Plan / Invoice</th>
            <th className="px-6 py-3 font-medium">Pending for</th>
            <th className="px-6 py-3 font-medium">Status</th>
            <th className="px-6 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {payments.map((payment) => {
            const days = getPendingDays(payment);
            const sending = sendingPaymentId === payment.id;
            return (
              <tr key={payment.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 font-medium text-gray-900">{payment.customer_name}</td>
                <td className="px-6 py-4 text-gray-600">{payment.customer_phone || "—"}</td>
                <td className="px-6 py-4 text-gray-700">₹{Number(payment.amount).toLocaleString()}</td>
                <td className="px-6 py-4 text-gray-600">{getPendingPaymentRef(payment)}</td>
                <td className="px-6 py-4 text-gray-600">
                  {days === 0 ? (
                    <span className="text-amber-600">Today</span>
                  ) : (
                    <span className={days > 7 ? "text-red-600" : ""}>{days} {days === 1 ? "day" : "days"}</span>
                  )}
                </td>
                <td className="px-6 py-4">
                  <Badge variant={STATUS_VARIANTS[payment.status]}>{getPaymentStatusLabel(payment.status)}</Badge>
                </td>
                <td className="px-6 py-4">
                  {canSend ? (
                    <div className="flex items-center justify-end">
                      <Button variant="outline" size="sm" disabled={sending} onClick={() => onSend(payment)}>
                        <Send className="h-4 w-4" />
                        {sending ? "Sending…" : "Send payment link"}
                      </Button>
                    </div>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}