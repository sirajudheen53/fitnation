"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Utensils, Sunrise, Sun, Cookie, Moon } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert, Spinner } from "@/components/ui";
import { fetchMealPlan, errorMessage } from "@/lib/api";
import type { MealPlan } from "@/types/nutrition";

const MEAL_ICONS = [
  { name: "breakfast", icon: Sunrise },
  { name: "lunch", icon: Sun },
  { name: "snack", icon: Cookie },
  { name: "dinner", icon: Moon },
];

export default function MealPlanDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const planId = params?.id;

  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace(`/login?next=/nutrition/meal-plan/${planId}`);
      return;
    }
    if (!planId) return;

    fetchMealPlan(planId, token)
      .then(setPlan)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [planId, router]);

  return (
    <DashboardLayout title={plan?.name ?? "Meal Plan"}>
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error && !plan ? (
        <Alert variant="error">{error}</Alert>
      ) : !plan ? (
        <Alert variant="warning">Meal plan not found.</Alert>
      ) : (
        <div className="space-y-6">
          <div>
            <Link
              href="/nutrition"
              className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800"
            >
              <ArrowLeft className="h-4 w-4" /> Back to nutrition
            </Link>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-gray-900">{plan.name}</h2>
                <p className="mt-1 text-sm text-gray-500">
                  {plan.description ?? "7-day meal plan"}
                </p>
              </div>
              <div className="rounded-lg bg-brand-50 px-4 py-2 text-center">
                <span className="block text-sm text-brand-700">
                  Target
                </span>
                <span className="text-lg font-semibold text-brand-700">
                  {plan.target_calories} cal
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {plan.days.map((day) => (
              <div
                key={day.id}
                className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3">
                  <h3 className="font-semibold text-gray-900">
                    Day {day.day_number} — {day.day_label}
                  </h3>
                  <span className="text-sm text-gray-500">
                    {day.total_calories} cal
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {day.meals.map((meal) => {
                    const icon =
                      MEAL_ICONS.find((m) =>
                        meal.name.toLowerCase().includes(m.name),
                      )?.icon ?? Utensils;
                    const Icon = icon;
                    return (
                      <div
                        key={meal.id}
                        className="rounded-lg border border-gray-100 bg-gray-50 p-4"
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 text-brand-600" />
                          <p className="font-medium text-gray-900">{meal.name}</p>
                          <span className="ml-auto text-xs text-gray-500">
                            {meal.total_calories} cal
                          </span>
                        </div>
                        <ul className="mt-3 space-y-1 text-sm text-gray-600">
                          {meal.items.map((item) => (
                            <li key={item.id} className="flex justify-between">
                              <span>
                                {item.name} ({item.quantity})
                              </span>
                              <span className="text-gray-400">
                                {item.calories} cal
                              </span>
                            </li>
                          ))}
                        </ul>
                        <div className="mt-3 flex gap-3 text-xs text-gray-500">
                          <span>P {meal.total_protein}g</span>
                          <span>C {meal.total_carbs}g</span>
                          <span>F {meal.total_fat}g</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
