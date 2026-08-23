"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Alert, Spinner } from "@/components/ui";
import { fetchInvoices, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import { getInvoiceStatusLabel, formatInvoiceDate } from "@/features/payments/components/invoiceHelpers";
import type { Invoice, InvoiceStatus } from "@/types/payment";

const STATUS_VARIANTS: Record<InvoiceStatus, "default" | "info" | "success" | "warning" | "danger"> = {
  draft: "default",
  issued: "info",
  paid: "success",
  overdue: "danger",
  cancelled: "warning",
};

export default function InvoicesPage() {
  const router = useRouter();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/payments")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/invoices");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchInvoices(authToken);
        setInvoices(res.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  return (
    <DashboardLayout title="Invoices">
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && invoices.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No invoices yet.</p>
        </div>
      )}
      {!loading && invoices.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-6 py-3 font-medium">Invoice #</th>
                <th className="px-6 py-3 font-medium">Customer</th>
                <th className="px-6 py-3 font-medium">Total</th>
                <th className="px-6 py-3 font-medium">Issue date</th>
                <th className="px-6 py-3 font-medium">Due date</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {invoices.map((invoice) => (
                <tr key={invoice.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">
                    {invoice.invoice_number}
                  </td>
                  <td className="px-6 py-4 text-gray-700">{invoice.customer_name}</td>
                  <td className="px-6 py-4 text-gray-700">
                    ₹{Number(invoice.total_amount).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {formatInvoiceDate(invoice.issue_date)}
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {formatInvoiceDate(invoice.due_date)}
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={STATUS_VARIANTS[invoice.status]}>
                      {getInvoiceStatusLabel(invoice.status)}
                    </Badge>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/invoices/${invoice.id}`}
                        className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                        aria-label="View invoice"
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
    </DashboardLayout>
  );
}
