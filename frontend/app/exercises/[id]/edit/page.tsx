"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ExerciseForm } from "@/features/exercises/components/ExerciseForm";
import { Spinner, Alert } from "@/components/ui";
import {
  fetchExercise,
  fetchExerciseCategories,
  updateExercise,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Exercise, ExerciseCategory, ExerciseFormData } from "@/types/exercise";

export default function EditExercisePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [categories, setCategories] = useState<ExerciseCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/exercises/new")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/exercises");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [exerciseData, categoryRes] = await Promise.all([
          fetchExercise(id, authToken),
          fetchExerciseCategories(authToken),
        ]);
        setExercise(exerciseData);
        setCategories(categoryRes.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router, userRole]);

  const handleSubmit = async (data: ExerciseFormData) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      await updateExercise(id, data, authToken);
      toast.success("Exercise updated");
      router.push(`/exercises/${id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Edit exercise">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !exercise && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && exercise && (
        <ExerciseForm
          exercise={exercise}
          categories={categories}
          submitLabel="Save changes"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
