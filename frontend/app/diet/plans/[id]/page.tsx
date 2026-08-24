"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Pencil, UserPlus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { NutritionBars } from "@/features/diet/components/NutritionBars";
import { Badge, Button, Alert, Spinner, Card, CardHeader, CardBody } from "@/components/ui";
import { fetchDietPlan, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { DietDay, DietGoal, DietPlan } from "@/types/diet";
import {
  GOAL_LABELS,
  MEAL_TYPE_LABELS,
  formatNumber,
} from "@/features/diet/components/nutritionHelpers";

const GOAL_VARIANTS: Record<DietGoal, "info" | "warning" | "success"> = {
  bulk: "info",
  cut: "warning",
  maintain: "success",
};

export default function DietPlanDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [plan, setPlan] = useState<DietPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
        const data = await fetchDietPlan(id, authToken);
        setPlan(data);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router, userRole]);

  const canEdit = userRole ? canAccessRoute(userRole, "/diet/plans/[id]/edit") : false;
  const canAssign = userRole ? canAccessRoute(userRole, "/diet/assign") : false;

  if (loading) {
    return (
      <DashboardLayout title="Diet plan">
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      </DashboardLayout>
    );
  }

  if (!plan) {
    return (
      <DashboardLayout title="Diet plan">
        {error && <Alert variant="error">{error}</Alert>}
      </DashboardLayout>
    );
  }

  const totalMacros = plan.days.reduce(
    (acc, d) => {
      for (const m of d.meals) {
        acc.calories += m.calories;
        acc.protein += m.protein;
        acc.carbs += m.carbs;
        acc.fat += m.fat;
      }
      return acc;
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );

  return (
    <DashboardLayout
      title={plan.name}
      actions={
        <div className="flex items-center gap-2">
          {canAssign && (
            <Link href="/diet/assign">
              <Button size="sm" variant="outline">
                <UserPlus className="h-4 w-4" /> Assign
              </Button>
            </Link>
          )}
          {canEdit && (
            <Link href={`/diet/plans/${plan.id}/edit`}>
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
              <Badge variant={GOAL_VARIANTS[plan.goal]}>{GOAL_LABELS[plan.goal]}</Badge>
              {plan.is_template ? (
                <Badge variant="info">Template</Badge>
              ) : (
                <Badge variant="success">Active</Badge>
              )}
              <Badge variant="default">{plan.duration_days} days</Badge>
            </div>
          </CardHeader>
          <CardBody>
            {plan.description && (
              <p className="mb-4 text-sm text-gray-600">{plan.description}</p>
            )}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {[
                { label: "Daily calories", value: `${formatNumber(plan.daily_calories)} kcal` },
                { label: "Protein", value: `${formatNumber(plan.protein_ratio)}%` },
                { label: "Carbs", value: `${formatNumber(plan.carb_ratio)}%` },
                { label: "Fat", value: `${formatNumber(plan.fat_ratio)}%` },
              ].map((row) => (
                <div key={row.label} className="rounded-lg bg-gray-50 p-4">
                  <p className="text-xs text-gray-500">{row.label}</p>
                  <p className="mt-1 text-lg font-semibold text-gray-900">{row.value}</p>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        {/* Macro visualization */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Nutrition overview</h2>
          </CardHeader>
          <CardBody>
            <NutritionBars
              calories={totalMacros.calories}
              protein={totalMacros.protein}
              carbs={totalMacros.carbs}
              fat={totalMacros.fat}
              targetCalories={plan.daily_calories}
            />
          </CardBody>
        </Card>

        {/* Daily breakdown */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Daily breakdown</h2>
          </CardHeader>
          <CardBody>
            {plan.days.length === 0 ? (
              <p className="text-sm text-gray-500">No days in this plan yet.</p>
            ) : (
              <div className="space-y-6">
                {plan.days.map((day: DietDay) => (
                  <div key={day.id} className="rounded-lg border border-gray-200 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="font-medium text-gray-900">Day {day.day_number}</h3>
                      <span className="text-sm text-gray-500">
                        {formatNumber(day.total_calories)} kcal
                      </span>
                    </div>
                    {day.notes && (
                      <p className="mb-3 text-sm text-gray-500">{day.notes}</p>
                    )}
                    {day.meals.length === 0 ? (
                      <p className="text-sm text-gray-400">No meals.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="border-b border-gray-100 text-xs uppercase text-gray-500">
                            <tr>
                              <th className="py-2 pr-3 font-medium">Meal</th>
                              <th className="py-2 pr-3 font-medium">Food</th>
                              <th className="py-2 pr-3 font-medium">Qty</th>
                              <th className="py-2 pr-3 font-medium">Cal</th>
                              <th className="py-2 pr-3 font-medium">Protein</th>
                              <th className="py-2 pr-3 font-medium">Carbs</th>
                              <th className="py-2 font-medium">Fat</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {day.meals.map((m) => (
                              <tr key={m.id}>
                                <td className="py-2 pr-3 text-gray-700">
                                  {MEAL_TYPE_LABELS[m.meal_type] ?? m.meal_type}
                                </td>
                                <td className="py-2 pr-3 font-medium text-gray-900">
                                  {m.food_item_name}
                                </td>
                                <td className="py-2 pr-3 text-gray-600">{m.quantity}</td>
                                <td className="py-2 pr-3 text-gray-700">
                                  {formatNumber(m.calories)}
                                </td>
                                <td className="py-2 pr-3 text-gray-700">
                                  {formatNumber(m.protein)}g
                                </td>
                                <td className="py-2 pr-3 text-gray-700">
                                  {formatNumber(m.carbs)}g
                                </td>
                                <td className="py-2 text-gray-700">
                                  {formatNumber(m.fat)}g
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
