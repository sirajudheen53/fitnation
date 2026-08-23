"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CustomerForm } from "@/features/customers/components/CustomerForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchCustomer, updateCustomer, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Customer, CustomerFormData } from "@/types/customer";

export default function CustomerEditPage() {
  const router = useRouter();
  const params = useParams();
  const id = Number(params.id);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const storedUser = typeof window !== "undefined"
      ? localStorage.getItem("fbos_user")
      : null;
    const role = storedUser ? (JSON.parse(storedUser).role as string) : null;
    if (role && !canAccessRoute(role, "/customers/new")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/customers/" + id + "/edit");
      return;
    }

    const authToken: string = token;

    async function load() {
      try {
        const data = await fetchCustomer(id, authToken);
        setCustomer(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const handleSubmit = async (data: CustomerFormData) => {
    const token = getToken();
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      await updateCustomer(id, data, token);
      router.push(`/customers/${id}`);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DashboardLayout title="Edit Customer">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error !== null && !customer && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {customer && (
        <CustomerForm
          customer={customer}
          onSubmit={handleSubmit}
          submitLabel="Save changes"
          error={error}
          loading={submitting}
        />
      )}
    </DashboardLayout>
  );
}
