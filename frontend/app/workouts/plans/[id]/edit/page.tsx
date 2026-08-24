"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { WorkoutPlanForm } from "@/features/workouts/components/WorkoutPlanForm";
import { Spinner, Alert } from "@/components/ui";
import {
  fetchWorkoutPlan,
  fetchExercises,
  updateWorkoutPlan,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Exercise } from "@/types/exercise";
import type { WorkoutPlan, WorkoutPlanFormData } from "@/types/workout";

export default function EditWorkoutPlanPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [plan, setPlan] = useState<WorkoutPlan | null>(null);
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
    if (userRole && !canAccessRoute(userRole, "/workouts/plans/[id]/edit")) {
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
        const [planData, exerciseRes] = await Promise.all([
          fetchWorkoutPlan(id, authToken),
          fetchExercises(authToken),
        ]);
        setPlan(planData);
        setExercises(exerciseRes.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router, userRole]);

  const handleSubmit = async (data: WorkoutPlanFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await updateWorkoutPlan(id, data, token);
      toast.success("Workout plan updated");
      router.push(`/workouts/plans/${id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Edit workout plan">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !plan && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && plan && (
        <WorkoutPlanForm
          plan={plan}
          exercises={exercises}
          submitLabel="Save changes"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
