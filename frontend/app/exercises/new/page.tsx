"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ExerciseForm } from "@/features/exercises/components/ExerciseForm";
import { Spinner, Alert } from "@/components/ui";
import {
  createExercise,
  fetchExerciseCategories,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { ExerciseCategory, ExerciseFormData } from "@/types/exercise";

export default function ExerciseCreatePage() {
  const router = useRouter();
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
      router.replace("/login?next=/exercises/new");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchExerciseCategories(authToken);
        setCategories(res.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const handleSubmit = async (data: ExerciseFormData) => {
    const token = getToken();
    if (!token) {
      setError("Authentication token not found.");
      return;
    }
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      const created = await createExercise(data, authToken);
      toast.success("Exercise created");
      router.push(`/exercises/${created.id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="New Exercise">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && categories.length === 0 && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && (
        <ExerciseForm
          categories={categories}
          submitLabel="Create exercise"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
