"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CreditCard, History, Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert } from "@/components/ui";
import { errorMessage, fetchRazorpayPayments } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { RazorpayPayment, RazorpayPaymentStatus } from "@/types/razorpay";
import { PaymentHistoryTable } from "@/features/razorpay/components/PaymentHistoryTable";
import { RazorpayCheckout, type CheckoutResult } from "@/features/razorpay/components/RazorpayCheckout";

export default function RazorpayPaymentsPage() {
  const router = useRouter();
  const [payments, setPayments] = useState<RazorpayPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<RazorpayPaymentStatus | "all">("all");
  const [activeTab, setActiveTab] = useState<"checkout" | "history">("checkout");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const stored = localStorage.getItem("fbos_user");
    return stored ? (JSON.parse(stored).role as string) : null;
  });

  const loadPayments = useCallback(() => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    fetchRazorpayPayments(token, status === "all" ? undefined : { status })
      .then((res) => setPayments(res.results))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [status]);

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/payments")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/payments/razorpay");
      return;
    }
    loadPayments();
  }, [router, userRole, loadPayments]);

  const handleComplete = (result: CheckoutResult) => {
    // After a successful payment, refresh history and jump to it.
    setActiveTab("history");
    loadPayments();
  };

  return (
    <DashboardLayout
      title="Razorpay Payments"
      actions={
        <Link
          href="/settings/razorpay"
          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <CreditCard className="h-4 w-4" />
          Configure Razorpay
        </Link>
      }
    >
      <div className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => setActiveTab("checkout")}
          className={
            activeTab === "checkout"
              ? "inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white"
              : "inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          }
        >
          <Plus className="h-4 w-4" />
          New payment
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={
            activeTab === "history"
              ? "inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white"
              : "inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          }
        >
          <History className="h-4 w-4" />
          Payment history
        </button>
      </div>

      {activeTab === "checkout" ? (
        <RazorpayCheckout onComplete={handleComplete} />
      ) : (
        <>
          {error && <Alert variant="error">{error}</Alert>}
          <PaymentHistoryTable
            payments={payments}
            loading={loading}
            error={error}
            status={status}
            onStatusChange={setStatus}
            onRefresh={loadPayments}
          />
        </>
      )}
    </DashboardLayout>
  );
}
