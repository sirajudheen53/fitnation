"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Apple } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { DietPlanCard } from "@/features/diet/components/DietPlanCard";
import { Button, Alert, Spinner } from "@/components/ui";
import {
  fetchDietPlans,
  duplicateDietPlan,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { DietGoal, DietPlan } from "@/types/diet";
import { GOAL_LABELS } from "@/features/diet/components/nutritionHelpers";

const GOALS = Object.keys(GOAL_LABELS) as DietGoal[];

export default function DietPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<DietPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [goalFilter, setGoalFilter] = useState("");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/diets")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/diet");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchDietPlans(authToken);
        setPlans(response.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/diet/plans/new") : false;
  const canEdit = userRole ? canAccessRoute(userRole, "/diet/plans/[id]/edit") : false;

  const handleGoalFilter = async (goal: string) => {
    setGoalFilter(goal);
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetchDietPlans(token, { goal: goal || undefined });
      setPlans(response.results);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleDuplicate = async (plan: DietPlan) => {
    const token = getToken();
    if (!token) return;
    try {
      await duplicateDietPlan(plan.id, token);
      const response = await fetchDietPlans(token, { goal: goalFilter || undefined });
      setPlans(response.results);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <DashboardLayout
      title="Diet plans"
      actions={
        canCreate ? (
          <Link href="/diet/plans/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> Create plan
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
          <div className="flex items-center gap-2">
            <Apple className="h-4 w-4 text-gray-400" />
            <select
              value={goalFilter}
              onChange={(e) => handleGoalFilter(e.target.value)}
              aria-label="Filter by goal"
              className="block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">All goals</option>
              {GOALS.map((g) => (
                <option key={g} value={g}>
                  {GOAL_LABELS[g]}
                </option>
              ))}
            </select>
          </div>

          {plans.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
              <p className="text-sm text-gray-500">No diet plans yet.</p>
              <p className="mt-1 text-sm text-gray-400">
                Create a plan to start building meal schedules.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {plans.map((plan) => (
                <DietPlanCard
                  key={plan.id}
                  plan={plan}
                  canEdit={canEdit}
                  onDuplicate={canCreate ? handleDuplicate : undefined}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
