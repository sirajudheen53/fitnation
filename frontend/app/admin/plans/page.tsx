"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Pencil, Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Button, Card, CardBody, Spinner } from "@/components/ui";
import {
  deactivateAdminPlan,
  errorMessage,
  fetchAdminPlans,
} from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import { PlanFormDialog } from "@/features/admin/components/PlanFormDialog";
import { PlanParityCheckCard } from "@/features/admin/components/PlanParityCheckCard";
import type { AdminSubscriptionPlan } from "@/types/admin";

/** "₹999.00" → "₹999" (keeps decimals only when they matter). */
function formatINR(value: string): string {
  const amount = Number(value);
  return `₹${Number.isFinite(amount) ? amount.toLocaleString("en-IN") : value}`;
}

export default function AdminPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<AdminSubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));
  const [formTarget, setFormTarget] = useState<
    { plan: AdminSubscriptionPlan | null } | null
  >(null);
  const [deactivateTarget, setDeactivateTarget] =
    useState<AdminSubscriptionPlan | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  useEffect(() => {
    if (user && user.role !== "platform_admin") {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/admin/plans");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        setPlans(await fetchAdminPlans(authToken));
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [router, user]);

  function replacePlan(updated: AdminSubscriptionPlan) {
    setPlans((list) => list.map((p) => (p.id === updated.id ? updated : p)));
  }

  async function deactivate(plan: AdminSubscriptionPlan) {
    const token = getToken();
    if (!token) return;
    setDeactivating(true);
    try {
      const updated = await deactivateAdminPlan(plan.id, token);
      setDeactivateTarget(null);
      replacePlan(updated);
      toast.success(`${updated.name} deactivated — existing gyms keep working.`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeactivating(false);
    }
  }

  return (
    <DashboardLayout
      title="Subscription Plans — Platform Admin"
      actions={
        <Button onClick={() => setFormTarget({ plan: null })}>
          <Plus className="mr-2 h-4 w-4" /> New Plan
        </Button>
      }
    >
      {error && (
        <Card className="mb-4">
          <CardBody className="text-sm text-red-600">{error}</CardBody>
        </Card>
      )}

      {!loading && !error && <PlanParityCheckCard plans={plans} />}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : plans.length === 0 && !error ? (
        <Card>
          <CardBody className="py-12 text-center text-sm text-gray-500">
            No subscription plans yet. Use “New Plan” to create the catalog new
            signups and onboarding will see.
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Plan</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Price</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Limits</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Sort</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Updated</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {plans.map((plan) => (
                    <tr
                      key={plan.id}
                      className={plan.is_active ? "hover:bg-gray-50" : "bg-gray-50/60"}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{plan.name}</div>
                        <div className="text-xs uppercase tracking-wide text-gray-500">
                          {plan.code}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {formatINR(plan.price_monthly)}/mo
                        <div className="text-xs text-gray-500">
                          {formatINR(plan.price_yearly)}/yr
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600">
                        {plan.max_branches} branches · {plan.max_customers} customers
                        <div className="text-gray-500">{plan.max_trainers} trainers</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-gray-600">{plan.sort_order}</td>
                      <td className="px-4 py-3">
                        <Badge variant={plan.is_active ? "success" : "default"}>
                          {plan.is_active ? "active" : "inactive"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {new Date(plan.updated_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Edit plan"
                            aria-label={`Edit ${plan.name}`}
                            onClick={() => setFormTarget({ plan })}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {plan.is_active && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:bg-red-50"
                              title="Deactivate plan"
                              aria-label={`Deactivate ${plan.name}`}
                              onClick={() => setDeactivateTarget(plan)}
                            >
                              Deactivate
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      {formTarget && (
        <PlanFormDialog
          plan={formTarget.plan}
          onClose={() => setFormTarget(null)}
          onSaved={(saved) => {
            if (formTarget.plan) {
              setFormTarget(null);
              replacePlan(saved);
              toast.success(`${saved.name} updated`);
            } else {
              setFormTarget(null);
              setPlans((list) => [...list, saved]);
              toast.success(`${saved.name} created`);
            }
          }}
        />
      )}

      {deactivateTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md">
            <CardBody className="space-y-4">
              <h3 className="text-base font-semibold text-gray-900">
                Deactivate {deactivateTarget.name}?
              </h3>
              <div className="space-y-2 text-sm text-gray-600">
                <p>
                  New signups and admin onboarding will no longer be able to select
                  “{deactivateTarget.code}”. Gyms already on this plan keep working —
                  the plan row is never deleted.
                </p>
                <p>You can reactivate it anytime by editing the plan.</p>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setDeactivateTarget(null)}
                  disabled={deactivating}
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  onClick={() => deactivate(deactivateTarget)}
                  disabled={deactivating}
                >
                  {deactivating ? "Deactivating…" : "Deactivate Plan"}
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </DashboardLayout>
  );
}
