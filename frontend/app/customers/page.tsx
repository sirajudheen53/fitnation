"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CustomerTable } from "@/features/customers/components/CustomerTable";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchCustomers, deleteCustomer, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import { useRouter } from "next/navigation";
import type { Customer } from "@/types/customer";

export default function CustomersPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/customers")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/customers");
      return;
    }

    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchCustomers(authToken);
        setCustomers(response.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/customers/new") : false;

  const handleDelete = async (customer: Customer) => {
    if (!confirm(`Delete customer "${customer.first_name} ${customer.last_name}"?`)) return;
    const token = getToken();
    if (!token) return;
    setDeleting(customer.id);
    try {
      await deleteCustomer(customer.id, token);
      setCustomers((prev) => prev.filter((c) => c.id !== customer.id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <DashboardLayout
      title="Customers"
      actions={
        canCreate ? (
          <Link href="/customers/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> New customer
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
        <CustomerTable
          customers={customers}
          onDelete={handleDelete}
          loading={deleting !== null}
        />
      )}
      {deleting !== null && (
        <div className="sr-only" role="status" aria-live="polite">
          Deleting customer…
        </div>
      )}
    </DashboardLayout>
  );
}
