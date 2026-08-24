"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { WorkoutPlanForm } from "@/features/workouts/components/WorkoutPlanForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchExercises, createWorkoutPlan, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Exercise } from "@/types/exercise";
import type { WorkoutPlanFormData } from "@/types/workout";

export default function NewWorkoutPlanPage() {
  const router = useRouter();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/workouts/plans/new")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/workouts/plans/new");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchExercises(authToken);
        setExercises(response.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const handleSubmit = async (data: WorkoutPlanFormData) => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/workouts/plans/new");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const plan = await createWorkoutPlan(data, token);
      toast.success("Workout plan created");
      router.push(`/workouts/plans/${plan.id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="New workout plan">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && exercises.length === 0 && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && (
        <WorkoutPlanForm
          exercises={exercises}
          submitLabel="Create plan"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
