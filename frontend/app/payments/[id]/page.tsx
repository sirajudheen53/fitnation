"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FileText, ArrowLeft } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardHeader, CardBody, Badge, Spinner, Alert } from "@/components/ui";
import {
  getPaymentStatusLabel,
  getPaymentMethodLabel,
  formatPaymentDate,
} from "@/features/payments/components/PaymentTable";
import { fetchPayment, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Payment, PaymentStatus } from "@/types/payment";

const STATUS_VARIANTS: Record<PaymentStatus, "success" | "warning" | "danger" | "info"> = {
  completed: "success",
  pending: "warning",
  failed: "danger",
  refunded: "info",
};

export default function PaymentDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [payment, setPayment] = useState<Payment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/payments");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchPayment(id, authToken);
        setPayment(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  return (
    <DashboardLayout title="Payment details">
      <div className="mb-4">
        <Link
          href="/payments"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to payments
        </Link>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && !payment && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && payment && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Payment</h2>
                <Badge variant={STATUS_VARIANTS[payment.status]}>
                  {getPaymentStatusLabel(payment.status)}
                </Badge>
              </div>
            </CardHeader>
            <CardBody>
              <dl className="space-y-4 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Customer</dt>
                  <dd className="font-medium text-gray-900">{payment.customer_name}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Amount</dt>
                  <dd className="font-semibold text-gray-900">
                    ₹{Number(payment.amount).toLocaleString()}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Method</dt>
                  <dd className="text-gray-900">{getPaymentMethodLabel(payment.method)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Date</dt>
                  <dd className="text-gray-900">{formatPaymentDate(payment.payment_date)}</dd>
                </div>
                {payment.membership_id && (
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Membership</dt>
                    <dd className="text-gray-900">#{payment.membership_id}</dd>
                  </div>
                )}
                {payment.notes && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-gray-500">Notes</dt>
                    <dd className="text-right text-gray-900">{payment.notes}</dd>
                  </div>
                )}
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Invoice</h2>
                {payment.invoice_id ? (
                  <Link
                    href={`/invoices/${payment.invoice_id}`}
                    className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    <FileText className="h-4 w-4" /> View invoice
                  </Link>
                ) : (
                  <Badge variant="warning">No invoice</Badge>
                )}
              </div>
            </CardHeader>
            <CardBody>
              {payment.invoice_id ? (
                <p className="text-sm text-gray-600">
                  An invoice has been generated for this payment. View it to print or download.
                </p>
              ) : (
                <p className="text-sm text-gray-600">
                  No invoice has been generated for this payment yet.
                </p>
              )}
            </CardBody>
          </Card>
        </div>
      )}
    </DashboardLayout>
  );
}
