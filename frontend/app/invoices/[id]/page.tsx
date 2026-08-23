"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Printer } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardHeader, CardBody, Badge, Spinner, Alert, Button } from "@/components/ui";
import { fetchInvoice, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { getInvoiceStatusLabel, formatInvoiceDate } from "@/features/payments/components/invoiceHelpers";
import type { Invoice, InvoiceStatus } from "@/types/payment";

const STATUS_VARIANTS: Record<InvoiceStatus, "default" | "info" | "success" | "warning" | "danger"> = {
  draft: "default",
  issued: "info",
  paid: "success",
  overdue: "danger",
  cancelled: "warning",
};

export default function InvoiceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/invoices");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchInvoice(id, authToken);
        setInvoice(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <DashboardLayout
      title="Invoice"
      actions={
        invoice ? (
          <Button size="sm" variant="outline" onClick={handlePrint}>
            <Printer className="h-4 w-4" /> Print
          </Button>
        ) : null
      }
    >
      <div className="mb-4">
        <Link
          href="/invoices"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to invoices
        </Link>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && !invoice && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && invoice && (
        <Card className="print:shadow-none print:border-0">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {invoice.invoice_number}
                </h2>
                <p className="text-sm text-gray-500">FitNation FBOS</p>
              </div>
              <Badge variant={STATUS_VARIANTS[invoice.status]}>
                {getInvoiceStatusLabel(invoice.status)}
              </Badge>
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <h3 className="text-sm font-medium text-gray-500">Billed to</h3>
                <p className="mt-1 font-medium text-gray-900">{invoice.customer_name}</p>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Issue date</span>
                  <span className="text-gray-900">{formatInvoiceDate(invoice.issue_date)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Due date</span>
                  <span className="text-gray-900">{formatInvoiceDate(invoice.due_date)}</span>
                </div>
                {invoice.paid_date && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Paid date</span>
                    <span className="text-gray-900">{formatInvoiceDate(invoice.paid_date)}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-8 space-y-2 border-t border-gray-100 pt-6 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Subtotal</span>
                <span className="text-gray-900">₹{Number(invoice.amount).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Tax</span>
                <span className="text-gray-900">₹{Number(invoice.tax_amount).toLocaleString()}</span>
              </div>
              <div className="flex justify-between border-t border-gray-100 pt-3 text-base font-semibold">
                <span className="text-gray-900">Total</span>
                <span className="text-gray-900">₹{Number(invoice.total_amount).toLocaleString()}</span>
              </div>
            </div>
          </CardBody>
        </Card>
      )}
    </DashboardLayout>
  );
}
