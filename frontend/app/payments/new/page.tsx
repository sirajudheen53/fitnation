"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PaymentForm } from "@/features/payments/components/PaymentForm";
import { createPayment, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { PaymentFormData } from "@/types/payment";

export default function NewPaymentPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const handleSubmit = async (data: PaymentFormData) => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/payments/new");
      return;
    }
    const authToken: string = token;
    setLoading(true);
    setError(null);
    try {
      await createPayment(data, authToken);
      toast.success("Payment recorded");
      router.push("/payments");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout title="Record payment">
      <PaymentForm
        submitLabel="Record payment"
        onSubmit={handleSubmit}
        error={error}
        loading={loading}
      />
    </DashboardLayout>
  );
}
