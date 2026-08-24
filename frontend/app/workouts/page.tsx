"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Dumbbell } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { WorkoutPlanCard } from "@/features/workouts/components/WorkoutPlanCard";
import { Button, Alert, Spinner } from "@/components/ui";
import {
  fetchWorkoutPlans,
  duplicateWorkoutPlan,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { WorkoutDifficulty, WorkoutGoal, WorkoutPlan } from "@/types/workout";
import {
  DIFFICULTY_LABELS,
  DIFFICULTY_OPTIONS,
  GOAL_LABELS,
  GOAL_OPTIONS,
} from "@/features/workouts/components/helpers";

export default function WorkoutsPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<WorkoutPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [goalFilter, setGoalFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/workouts")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/workouts");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchWorkoutPlans(authToken);
        setPlans(response.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/workouts/plans/new") : false;
  const canEdit = userRole ? canAccessRoute(userRole, "/workouts/plans/[id]/edit") : false;

  const applyFilters = async (goal: string, difficulty: string) => {
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetchWorkoutPlans(token, {
        goal: goal || undefined,
        difficulty: difficulty || undefined,
      });
      setPlans(response.results);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleGoalFilter = (goal: string) => {
    setGoalFilter(goal);
    void applyFilters(goal, difficultyFilter);
  };

  const handleDifficultyFilter = (difficulty: string) => {
    setDifficultyFilter(difficulty);
    void applyFilters(goalFilter, difficulty);
  };

  const handleDuplicate = async (plan: WorkoutPlan) => {
    const token = getToken();
    if (!token) return;
    try {
      await duplicateWorkoutPlan(plan.id, token);
      const response = await fetchWorkoutPlans(token, {
        goal: goalFilter || undefined,
        difficulty: difficultyFilter || undefined,
      });
      setPlans(response.results);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <DashboardLayout
      title="Workout plans"
      actions={
        canCreate ? (
          <Link href="/workouts/plans/new">
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
          <div className="flex flex-wrap items-center gap-2">
            <Dumbbell className="h-4 w-4 text-gray-400" />
            <select
              value={goalFilter}
              onChange={(e) => handleGoalFilter(e.target.value)}
              aria-label="Filter by goal"
              className="block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">All goals</option>
              {GOAL_OPTIONS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
            <select
              value={difficultyFilter}
              onChange={(e) => handleDifficultyFilter(e.target.value)}
              aria-label="Filter by difficulty"
              className="block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">All difficulties</option>
              {DIFFICULTY_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>

          {plans.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
              <p className="text-sm text-gray-500">No workout plans yet.</p>
              <p className="mt-1 text-sm text-gray-400">
                Create a plan to start building workout schedules.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {plans.map((plan) => (
                <WorkoutPlanCard
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
