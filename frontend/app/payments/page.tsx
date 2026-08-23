"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PaymentTable, type PaymentFilters } from "@/features/payments/components/PaymentTable";
import { RevenueSummary } from "@/features/payments/components/RevenueSummary";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchPayments, fetchRevenueSummary, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Payment, RevenueSummary as RevenueSummaryData } from "@/types/payment";

export default function PaymentsPage() {
  const router = useRouter();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [summary, setSummary] = useState<RevenueSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<PaymentFilters>({});
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
          <RevenueSummary summary={summary ?? { today: 0, this_week: 0, this_month: 0 }} />
          <PaymentTable
            payments={filteredPayments}
            filters={filters}
            onFilterChange={setFilters}
          />
        </div>
      )}
    </DashboardLayout>
  );
}
