"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CustomerForm } from "@/features/customers/components/CustomerForm";
import { createCustomer, createPayment, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { CustomerFormData } from "@/types/customer";

export default function CustomerCreatePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const storedUser = typeof window !== "undefined"
      ? localStorage.getItem("fbos_user")
      : null;
    const role = storedUser ? (JSON.parse(storedUser).role as string) : null;
    if (role && !canAccessRoute(role, "/customers/new")) {
      router.replace("/unauthorized");
    }
  }, [router]);

  const handleSubmit = async (data: CustomerFormData) => {
    const token = getToken();
    if (!token) {
      setError("Authentication token not found.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const customer = await createCustomer(data, token);
      // The admission fee is a separate Payment row (kind=admission). The
      // customer itself is already created — a fee failure must not send the
      // owner back to the form, only warn that the fee wasn't recorded.
      if (data.admission_fee && data.admission_fee.amount > 0) {
        const fee = data.admission_fee;
        try {
          await createPayment(
            {
              customer_id: customer.id,
              amount: fee.amount,
              method: fee.method,
              status: fee.status,
              kind: "admission",
            },
            token,
          );
          toast.success(
            fee.status === "completed"
              ? "Customer created and admission fee recorded"
              : "Customer created; admission fee marked pending",
          );
        } catch (feeErr) {
          toast.warning(
            `Customer created, but the admission fee wasn't recorded: ${errorMessage(feeErr)}`,
          );
        }
      } else {
        toast.success("Customer created");
      }
      router.push("/customers");
    } catch (err) {
      setError(err);
      setLoading(false);
    }
  };

  return (
    <DashboardLayout title="New Customer">
      <CustomerForm
        onSubmit={handleSubmit}
        submitLabel="Create customer"
        error={error}
        loading={loading}
      />
    </DashboardLayout>
  );
}
