"use client";

import Link from "next/link";
import { Send, Wallet } from "lucide-react";
import { Button, Card, CardHeader, CardBody, DeletedUserBadge } from "@/components/ui";
import type { PendingPayment } from "@/types/dashboard";

interface PendingPaymentsProps {
  payments: PendingPayment[];
  loading?: boolean;
  /**
   * Row action on a pending payment (issue #79): intimate the member on
   * WhatsApp with the payment link — same send-link backend as the
   * /payments queue. Omit (or pass ``canSend={false}``) to hide the button.
   */
  onSend?: (payment: PendingPayment) => void;
  /** The payment whose link is currently sending (that row's action disables). */
  sendingPaymentId?: number | null;
  /** Hidden without ``payments.record_payment`` (mirrors the route guard). */
  canSend?: boolean;
}

export function formatDueDate(date: string | null): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString();
}

export function PendingPayments({
  payments,
  loading = false,
  onSend,
  sendingPaymentId = null,
  canSend = false,
}: PendingPaymentsProps) {
  if (loading) {
    return (
      <Card>
        <CardBody>
          <div className="h-64 animate-pulse rounded-lg bg-gray-100" />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Pending payments</h2>
      </CardHeader>
      <CardBody>
        {payments.length === 0 ? (
          <div className="py-8 text-center">
            <Wallet className="mx-auto h-10 w-10 text-gray-300" />
            <p className="mt-3 text-sm text-gray-500">No pending payments.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {payments.map((payment) => {
              const sending = sendingPaymentId === payment.id;
              return (
                <li key={payment.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium text-gray-900">
                      {payment.customer_name}
                      {payment.customer_is_deleted ? <DeletedUserBadge className="ml-2" /> : null}
                    </p>
                    <p className="text-xs text-gray-500">Due {formatDueDate(payment.due_date)}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-gray-900">
                      ₹{Number(payment.amount).toLocaleString()}
                    </p>
                    <div className="flex items-center justify-end gap-3">
                      {canSend && onSend ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={sending}
                          onClick={() => onSend(payment)}
                        >
                          <Send className="h-4 w-4" />
                          {sending ? "Sending…" : "Intimate on WhatsApp"}
                        </Button>
                      ) : null}
                      <Link
                        href={`/payments/new`}
                        className="text-xs font-medium text-brand-600 hover:text-brand-700"
                      >
                        Record payment
                      </Link>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
