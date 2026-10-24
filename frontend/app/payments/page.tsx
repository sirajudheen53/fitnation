"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PaymentTable, type PaymentFilters } from "@/features/payments/components/PaymentTable";
import { PendingPaymentTable } from "@/features/payments/components/PendingPaymentTable";
import { RevenueSummary } from "@/features/payments/components/RevenueSummary";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchPayments, fetchRevenueSummary, sendPaymentLink, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute, hasAnyPermission } from "@/lib/permissions";
import type { Payment, RevenueSummary as RevenueSummaryData } from "@/types/payment";

/** Queue views on the payments page (issue #72): the ledger and the pending queue. */
type PaymentsView = "all" | "pending";

const VIEW_TABS: { key: PaymentsView; label: string }[] = [
  { key: "all", label: "All payments" },
  { key: "pending", label: "Pending" },
];

export default function PaymentsPage() {
  const router = useRouter();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [summary, setSummary] = useState<RevenueSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<PaymentFilters>({});
  const [view, setView] = useState<PaymentsView>("all");
  const [sendingPaymentId, setSendingPaymentId] = useState<number | null>(null);
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
      router.replace("/login?next=/payments");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [paymentRes, summaryRes] = await Promise.all([
          fetchPayments(authToken),
          fetchRevenueSummary(authToken),
        ]);
        setPayments(paymentRes.results);
        setSummary(summaryRes);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const filteredPayments = useMemo(() => {
    return payments.filter((p) => {
      if (filters.customer) {
        const q = filters.customer.toLowerCase();
        if (!p.customer_name.toLowerCase().includes(q)) return false;
      }
      if (filters.status && p.status !== filters.status) return false;
      if (filters.from && p.payment_date.slice(0, 10) < filters.from) return false;
      if (filters.to && p.payment_date.slice(0, 10) > filters.to) return false;
      return true;
    });
  }, [payments, filters]);

  const canCreate = userRole ? canAccessRoute(userRole, "/payments/new") : false;
  const canSendLink = userRole ? hasAnyPermission(userRole, ["payments.record_payment"]) : false;

  const pendingPayments = useMemo(() => payments.filter((p) => p.status === "pending"), [payments]);

  /**
   * Row action on the pending queue (issue #72): create a Razorpay payment
   * link and push it to the member over WhatsApp (backend falls back to SMS
   * then email). The backend cooldown surfaces as "already_sent".
   */
  const handleSendLink = async (payment: Payment) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSendingPaymentId(payment.id);
    try {
      const outcome = await sendPaymentLink(payment.id, authToken);
      if (outcome.status === "sent") {
        toast.success(`Payment link sent to ${payment.customer_name} over ${outcome.channel}`);
      } else if (outcome.status === "already_sent") {
        toast.info(`A link was sent to ${payment.customer_name} recently — try again later.`);
      } else {
        toast.error(outcome.reason || `Could not send a payment link to ${payment.customer_name}`);
      }
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSendingPaymentId(null);
    }
  };

  return (
    <DashboardLayout
      title="Payments"
      actions={
        canCreate ? (
          <Link href="/payments/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> Record payment
            </Button>
          </Link>
        ) : null
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <div className="space-y-6">
          <div
            className="flex gap-1 rounded-xl border border-gray-200 bg-white p-1"
            role="tablist"
            aria-label="Payments views"
          >
            {VIEW_TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={view === key}
                onClick={() => setView(key)}
                className={
                  view === key
                    ? "rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white"
                    : "rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
                }
              >
                {label}
                {key === "pending" && pendingPayments.length > 0 && (
                  <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                    {pendingPayments.length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {view === "pending" ? (
            <PendingPaymentTable
              payments={pendingPayments}
              sendingPaymentId={sendingPaymentId}
              onSend={handleSendLink}
              canSend={canSendLink}
            />
          ) : (
            <>
              <RevenueSummary summary={summary ?? { today: 0, this_week: 0, this_month: 0 }} />
              <PaymentTable payments={filteredPayments} filters={filters} onFilterChange={setFilters} />
            </>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
