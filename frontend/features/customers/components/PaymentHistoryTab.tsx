"use client";

import Link from "next/link";
import { ArrowRight, CreditCard } from "lucide-react";
import { Card, CardHeader, CardBody, Button } from "@/components/ui";
import type { Customer } from "@/types/customer";

interface PaymentHistoryTabProps {
  customer: Customer;
}

export function PaymentHistoryTab({ customer }: PaymentHistoryTabProps) {
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
                  Includes membership renewals, marketplace orders and personal training charges.
                </p>
              </div>
            </div>
            <Link href={`/payments?customer=${encodeURIComponent(customer.email)}`}>
              <Button size="sm">
                View payment history <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
