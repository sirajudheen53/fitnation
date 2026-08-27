"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Receipt } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert, Card, CardBody, CardHeader, Spinner } from "@/components/ui";
import { errorMessage, fetchRazorpayPayments } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { RazorpayPayment } from "@/types/razorpay";
import { formatRazorpayDate, getRazorpayMethodLabel, RazorpayStatusBadge } from "@/features/razorpay/components/RazorpayStatusBadge";

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-3 last:border-0">
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className="text-sm font-medium text-gray-900">{value}</dd>
    </div>
  );
}

export default function RazorpayPaymentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [payment, setPayment] = useState<RazorpayPayment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/payments/razorpay");
      return;
    }
    fetchRazorpayPayments(token)
      .then((res) => {
        const found = res.results.find((p) => String(p.id) === String(id));
        if (!found) {
          setError("Payment not found.");
        } else {
          setPayment(found);
        }
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return (
    <DashboardLayout
      title="Payment detail"
      actions={
        <Link
          href="/payments/razorpay"
          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to payments
        </Link>
      }
    >
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error ? (
        <Alert variant="error">{error}</Alert>
      ) : payment ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
                  <Receipt className="h-5 w-5 text-gray-400" />
                  Payment #{payment.id}
                </h2>
                <RazorpayStatusBadge status={payment.status} />
              </div>
            </CardHeader>
            <CardBody>
              <dl>
                <DetailRow label="Amount" value={`₹${Number(payment.amount).toLocaleString("en-IN")}`} />
                <DetailRow label="Payment method" value={getRazorpayMethodLabel(payment.payment_method)} />
                <DetailRow label="Customer" value={`#${payment.customer}`} />
                <DetailRow label="Membership" value={payment.membership ? `#${payment.membership}` : "—"} />
                <DetailRow label="Transaction ID" value={payment.transaction_id || "—"} />
                <DetailRow label="Razorpay order ID" value={payment.razorpay_order_id || "—"} />
                <DetailRow label="Razorpay payment ID" value={payment.razorpay_payment_id || "—"} />
                <DetailRow label="Paid at" value={formatRazorpayDate(payment.paid_at)} />
                <DetailRow label="Created" value={formatRazorpayDate(payment.created_at)} />
              </dl>
            </CardBody>
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <h3 className="text-sm font-semibold text-gray-900">Notes</h3>
            </CardHeader>
            <CardBody>
              {payment.notes ? (
                <p className="whitespace-pre-wrap text-sm text-gray-600">{payment.notes}</p>
              ) : (
                <p className="text-sm text-gray-400">No notes for this payment.</p>
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}
    </DashboardLayout>
  );
}
