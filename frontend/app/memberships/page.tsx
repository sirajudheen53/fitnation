"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Pencil } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { MembershipTable } from "@/features/memberships/components/MembershipTable";
import { Button, Alert, Spinner, Card, CardHeader, CardBody, Badge } from "@/components/ui";
import {
  fetchMembershipPlans,
  fetchMemberships,
  cancelMembership,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Membership, MembershipPlan } from "@/types/membership";

export default function MembershipsPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<number | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/memberships")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/memberships");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [planRes, membershipRes] = await Promise.all([
          fetchMembershipPlans(authToken),
          fetchMemberships(authToken),
        ]);
        setPlans(planRes.results);
        setMemberships(membershipRes.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/memberships/plans/new") : false;
  const canAssign = userRole ? canAccessRoute(userRole, "/memberships/assign") : false;

  const handleCancel = async (membership: Membership) => {
    if (!confirm(`Cancel membership for "${membership.customer_name}"?`)) return;
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setCancelling(membership.id);
    try {
      await cancelMembership(membership.id, authToken);
      setMemberships((prev) =>
        prev.map((m) => (m.id === membership.id ? { ...m, status: "cancelled" } : m)),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCancelling(null);
    }
  };

  return (
    <DashboardLayout
      title="Memberships"
      actions={
        <div className="flex items-center gap-2">
          {canAssign && (
            <Link href="/memberships/assign">
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4" /> Assign
              </Button>
            </Link>
          )}
          {canCreate && (
            <Link href="/memberships/plans/new">
              <Button size="sm">
                <Plus className="h-4 w-4" /> New plan
              </Button>
            </Link>
          )}
        </div>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <div className="space-y-8">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Membership plans</h2>
            </CardHeader>
            <CardBody>
              {plans.length === 0 ? (
                <p className="text-sm text-gray-500">No plans created yet.</p>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {plans.map((plan) => (
                    <div
                      key={plan.id}
                      className="flex flex-col justify-between rounded-xl border border-gray-200 p-5"
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <h3 className="font-semibold text-gray-900">{plan.name}</h3>
                          {plan.is_active ? (
                            <Badge variant="success">Active</Badge>
                          ) : (
                            <Badge variant="danger">Inactive</Badge>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-gray-500">
                          {plan.duration_days} days
                        </p>
                        <p className="mt-2 text-lg font-semibold text-brand-600">
                          ₹{Number(plan.price).toLocaleString()}
                        </p>
                        {plan.description && (
                          <p className="mt-2 text-sm text-gray-600">{plan.description}</p>
                        )}
                      </div>
                      <div className="mt-4 flex items-center gap-2">
                        <Link
                          href={`/memberships/plans/${plan.id}/edit`}
                          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                          aria-label="Edit plan"
                        >
                          <Pencil className="h-4 w-4" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Active memberships</h2>
            </CardHeader>
            <CardBody>
              <MembershipTable
                memberships={memberships}
                onCancel={handleCancel}
                loading={cancelling !== null}
              />
              {cancelling !== null && (
                <div className="sr-only" role="status" aria-live="polite">
                  Cancelling membership…
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      )}
    </DashboardLayout>
  );
}
