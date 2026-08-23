"use client";

import Link from "next/link";
import { Wallet } from "lucide-react";
import { Card, CardHeader, CardBody } from "@/components/ui";
import type { PendingPayment } from "@/types/dashboard";

interface PendingPaymentsProps {
  payments: PendingPayment[];
  loading?: boolean;
}

export function formatDueDate(date: string | null): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString();
}

export function PendingPayments({ payments, loading = false }: PendingPaymentsProps) {
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
            {payments.map((payment) => (
              <li key={payment.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium text-gray-900">{payment.customer_name}</p>
                  <p className="text-xs text-gray-500">Due {formatDueDate(payment.due_date)}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-gray-900">
                    ₹{Number(payment.amount).toLocaleString()}
                  </p>
                  <Link
                    href={`/payments/new`}
                    className="text-xs font-medium text-brand-600 hover:text-brand-700"
                  >
                    Record payment
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
