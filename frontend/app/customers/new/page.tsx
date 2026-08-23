"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CustomerForm } from "@/features/customers/components/CustomerForm";
import { createCustomer, errorMessage } from "@/lib/api";
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
      await createCustomer(data, token);
      router.push("/customers");
    } catch (err) {
      setError(err);
    } finally {
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
