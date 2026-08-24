"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Pencil, UserPlus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Button, Alert, Spinner, Card, CardHeader, CardBody } from "@/components/ui";
import { fetchWorkoutPlan, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { WorkoutDay, WorkoutDifficulty, WorkoutGoal, WorkoutPlan } from "@/types/workout";
import {
  DIFFICULTY_LABELS,
  GOAL_LABELS,
  dayLabel,
  difficultyBadgeVariant,
  goalBadgeVariant,
} from "@/features/workouts/components/helpers";

export default function WorkoutPlanDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [plan, setPlan] = useState<WorkoutPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
        const data = await fetchWorkoutPlan(id, authToken);
        setPlan(data);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router, userRole]);

  const canEdit = userRole ? canAccessRoute(userRole, "/workouts/plans/[id]/edit") : false;
  const canAssign = userRole ? canAccessRoute(userRole, "/workouts/assign") : false;

  if (loading) {
    return (
      <DashboardLayout title="Workout plan">
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  if (!plan) {
    return (
      <DashboardLayout title="Workout plan">
        {error && <Alert variant="error">{error}</Alert>}
      </DashboardLayout>
    );
  }

  const totalExercises = plan.days.reduce(
    (acc, d) => acc + d.exercises.length,
    0,
  );

  return (
    <DashboardLayout
      title={plan.name}
      actions={
        <div className="flex items-center gap-2">
          {canAssign && (
            <Link href="/workouts/assign">
              <Button size="sm" variant="outline">
                <UserPlus className="h-4 w-4" /> Assign
              </Button>
            </Link>
          )}
          {canEdit && (
            <Link href={`/workouts/plans/${plan.id}/edit`}>
              <Button size="sm">
                <Pencil className="h-4 w-4" /> Edit
              </Button>
            </Link>
          )}
        </div>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}

      <div className="space-y-6">
        {/* Overview */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={goalBadgeVariant(plan.goal)}>{GOAL_LABELS[plan.goal]}</Badge>
              <Badge variant={difficultyBadgeVariant(plan.difficulty)}>
                {DIFFICULTY_LABELS[plan.difficulty]}
              </Badge>
              {plan.is_template ? (
                <Badge variant="info">Template</Badge>
              ) : (
                <Badge variant="success">Active</Badge>
              )}
              <Badge variant="default">{plan.duration_weeks} weeks</Badge>
            </div>
          </CardHeader>
          <CardBody>
            {plan.description && (
              <p className="mb-4 text-sm text-gray-600">{plan.description}</p>
            )}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
              {[
                { label: "Goal", value: GOAL_LABELS[plan.goal] },
                { label: "Difficulty", value: DIFFICULTY_LABELS[plan.difficulty] },
                { label: "Days", value: String(plan.days.length) },
                { label: "Exercises", value: String(totalExercises) },
                { label: "Duration", value: `${plan.duration_weeks} weeks` },
                { label: "Type", value: plan.is_template ? "Template" : "Active" },
              ].map((row) => (
                <div key={row.label} className="rounded-lg bg-gray-50 p-4">
                  <p className="text-xs text-gray-500">{row.label}</p>
                  <p className="mt-1 text-lg font-semibold text-gray-900">{row.value}</p>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        {/* Weekly view */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Weekly view</h2>
          </CardHeader>
          <CardBody>
            {plan.days.length === 0 ? (
              <p className="text-sm text-gray-500">No days in this plan yet.</p>
            ) : (
              <div className="space-y-6">
                {plan.days.map((day: WorkoutDay) => (
                  <div key={day.id} className="rounded-lg border border-gray-200 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="font-medium text-gray-900">{dayLabel(day)}</h3>
                      <span className="text-sm text-gray-500">
                        {day.exercises.length} exercises
                      </span>
                    </div>
                    {day.notes && (
                      <p className="mb-3 text-sm text-gray-500">{day.notes}</p>
                    )}
                    {day.exercises.length === 0 ? (
                      <p className="text-sm text-gray-400">No exercises.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="border-b border-gray-100 text-xs uppercase text-gray-500">
                            <tr>
                              <th className="py-2 pr-3 font-medium">#</th>
                              <th className="py-2 pr-3 font-medium">Exercise</th>
                              <th className="py-2 pr-3 font-medium">Sets</th>
                              <th className="py-2 pr-3 font-medium">Reps</th>
                              <th className="py-2 pr-3 font-medium">Rest</th>
                              <th className="py-2 pr-3 font-medium">Tempo</th>
                              <th className="py-2 pr-3 font-medium">RPE</th>
                              <th className="py-2 font-medium">Alternate</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {day.exercises.map((ex) => (
                              <tr key={ex.id}>
                                <td className="py-2 pr-3 text-gray-500">{ex.order + 1}</td>
                                <td className="py-2 pr-3 font-medium text-gray-900">
                                  {ex.exercise_name}
                                </td>
                                <td className="py-2 pr-3 text-gray-700">{ex.sets}</td>
                                <td className="py-2 pr-3 text-gray-700">{ex.reps}</td>
                                <td className="py-2 pr-3 text-gray-700">
                                  {ex.rest_seconds}s
                                </td>
                                <td className="py-2 pr-3 text-gray-700">{ex.tempo || "—"}</td>
                                <td className="py-2 pr-3 text-gray-700">{ex.rpe ?? "—"}</td>
                                <td className="py-2 text-gray-700">
                                  {ex.alternate_exercise_name || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </DashboardLayout>
  );
}
