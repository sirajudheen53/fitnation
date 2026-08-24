"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, LayoutGrid, List } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ExerciseCard } from "@/features/exercises/components/ExerciseCard";
import { ExerciseFilters } from "@/features/exercises/components/ExerciseFilters";
import { Button, Alert, Spinner } from "@/components/ui";
import {
  fetchExercises,
  fetchExerciseCategories,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type {
  Exercise,
  ExerciseCategory,
  ExerciseFilters as ExerciseFiltersType,
} from "@/types/exercise";

type ViewMode = "grid" | "list";

export default function ExercisesPage() {
  const router = useRouter();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [categories, setCategories] = useState<ExerciseCategory[]>([]);
  const [filters, setFilters] = useState<ExerciseFiltersType>({});
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/exercises")) {
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
        const [exerciseRes, categoryRes] = await Promise.all([
          fetchExercises(authToken),
          fetchExerciseCategories(authToken),
        ]);
        setExercises(exerciseRes.results);
        setCategories(categoryRes.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;

    let active = true;
    async function loadFiltered() {
      try {
        const res = await fetchExercises(authToken, filters);
        if (active) setExercises(res.results);
      } catch (err) {
        if (active) setError(errorMessage(err));
      }
    }
    loadFiltered();
    return () => {
      active = false;
    };
  }, [filters]);

  const canCreate = userRole ? canAccessRoute(userRole, "/exercises/new") : false;

  return (
    <DashboardLayout
      title="Exercise Library"
      actions={
        canCreate ? (
          <Link href="/exercises/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> Create exercise
            </Button>
          </Link>
        ) : null
      }
    >
      {error && <Alert variant="error">{error}</Alert>}

      <div className="mb-4 flex items-center justify-between gap-3">
        <ExerciseFilters
          categories={categories}
          filters={filters}
          onChange={setFilters}
        />
        <div className="flex shrink-0 items-center gap-1 rounded-lg border border-gray-200 bg-white p-1">
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={`rounded-md p-2 ${
              viewMode === "grid"
                ? "bg-brand-50 text-brand-700"
                : "text-gray-500 hover:bg-gray-50"
            }`}
            aria-label="Grid view"
            aria-pressed={viewMode === "grid"}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setViewMode("list")}
            className={`rounded-md p-2 ${
              viewMode === "list"
                ? "bg-brand-50 text-brand-700"
                : "text-gray-500 hover:bg-gray-50"
            }`}
            aria-label="List view"
            aria-pressed={viewMode === "list"}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}

      {!loading && exercises.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No exercises found.</p>
        </div>
      )}

      {!loading && exercises.length > 0 && viewMode === "grid" && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {exercises.map((exercise) => (
            <ExerciseCard key={exercise.id} exercise={exercise} canEdit={canCreate} />
          ))}
        </div>
      )}

      {!loading && exercises.length > 0 && viewMode === "list" && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Difficulty
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Muscle groups
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {exercises.map((exercise) => (
                <tr key={exercise.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <Link
                      href={`/exercises/${exercise.id}`}
                      className="font-medium text-gray-900 hover:text-brand-600"
                    >
                      {exercise.name}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {exercise.category_name || "—"}
                  </td>
                  <td className="px-6 py-4 text-sm capitalize text-gray-600">
                    {exercise.difficulty}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {exercise.muscle_groups.length
                      ? exercise.muscle_groups.join(", ")
                      : "—"}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      href={`/exercises/${exercise.id}`}
                      className="text-sm font-medium text-brand-600 hover:text-brand-700"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DashboardLayout>
  );
}
