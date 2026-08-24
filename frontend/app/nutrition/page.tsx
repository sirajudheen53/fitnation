"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Utensils, Flame, Beef, Wheat, Droplet, ShoppingBasket, Plus, Sparkles } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert, Spinner, Input } from "@/components/ui";
import { fetchMealPlans, generateMealPlan, errorMessage } from "@/lib/api";
import type { MealPlan } from "@/types/nutrition";

interface MacroBar {
  key: "calories" | "protein" | "carbs" | "fat";
  label: string;
  value: number;
  target: number;
  color: string;
}

function MacroProgress({ label, value, target, color }: MacroBar) {
  const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">
          {value} / {target}
        </span>
      </div>
      <div className="mt-2 h-2 w-full rounded-full bg-gray-100">
        <div
          className={`h-2 rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function NutritionPage() {
  const router = useRouter();
  const [mealPlans, setMealPlans] = useState<MealPlan[]>([]);
  const [targetCalories, setTargetCalories] = useState("2000");
  const [cuisine, setCuisine] = useState("");
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/nutrition");
      return;
    }
    fetchMealPlans(token)
      .then((data) => setMealPlans(data.results))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [router]);

  const current = mealPlans[0];

  const macros: MacroBar[] = current
    ? [
        {
          key: "calories",
          label: "Calories",
          value: current.days[0]?.total_calories ?? 0,
          target: current.target_calories,
          color: "bg-brand-600",
        },
        {
          key: "protein",
          label: "Protein (g)",
          value: current.days[0]?.total_protein ?? 0,
          target: Math.round(current.target_calories * 0.15 / 4),
          color: "bg-blue-500",
        },
        {
          key: "carbs",
          label: "Carbs (g)",
          value: current.days[0]?.total_carbs ?? 0,
          target: Math.round(current.target_calories * 0.5 / 4),
          color: "bg-green-500",
        },
        {
          key: "fat",
          label: "Fat (g)",
          value: current.days[0]?.total_fat ?? 0,
          target: Math.round(current.target_calories * 0.35 / 9),
          color: "bg-amber-500",
        },
      ]
    : [];

  const handleGenerate = async () => {
    const token = getToken();
    if (!token) return;
    setGenerating(true);
    setError(null);
    try {
      const plan = await generateMealPlan(token, {
        target_calories: Number(targetCalories) || 2000,
        cuisine: cuisine || undefined,
      });
      setMealPlans((prev) => [plan, ...prev]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <DashboardLayout
      title="Nutrition"
      actions={
        <Link href="/nutrition/shopping-list">
          <Button variant="outline" size="sm">
            <ShoppingBasket className="mr-1 h-4 w-4" /> Shopping list
          </Button>
        </Link>
      }
    >
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error && mealPlans.length === 0 ? (
        <Alert variant="error">{error}</Alert>
      ) : (
        <div className="space-y-6">
          {/* Generate plan card */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="flex items-center gap-2 font-semibold text-gray-900">
              <Sparkles className="h-4 w-4 text-brand-600" /> Generate meal plan
            </h3>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
              <Input
                type="number"
                label="Target calories"
                value={targetCalories}
                onChange={(e) => setTargetCalories(e.target.value)}
              />
              <Input
                label="Cuisine (optional)"
                value={cuisine}
                onChange={(e) => setCuisine(e.target.value)}
                placeholder="e.g. Indian, Mediterranean"
              />
              <div className="flex items-end">
                <Button
                  className="w-full"
                  onClick={handleGenerate}
                  disabled={generating}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {generating ? "Generating..." : "Generate"}
                </Button>
              </div>
            </div>
            {error && mealPlans.length > 0 && (
              <Alert variant="error" className="mt-3">{error}</Alert>
            )}
          </div>

          {current ? (
            <>
              {/* Current plan summary */}
              <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
                      <Utensils className="h-5 w-5 text-brand-600" />
                      {current.name}
                    </h3>
                    <p className="mt-1 text-sm text-gray-500">
                      {current.description ?? "Your current meal plan"}
                    </p>
                  </div>
                  <Link href={`/nutrition/meal-plan/${current.id}`}>
                    <Button variant="outline" size="sm">View plan</Button>
                  </Link>
                </div>
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {macros.map((m) => (
                    <MacroProgress
                      key={m.key}
                      label={m.label}
                      value={m.value}
                      target={m.target}
                      color={m.color}
                    />
                  ))}
                </div>
              </div>

              {/* Other plans */}
              {mealPlans.length > 1 && (
                <div>
                  <h4 className="mb-3 font-medium text-gray-900">
                    Previous plans
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {mealPlans.slice(1).map((plan) => (
                      <Link
                        key={plan.id}
                        href={`/nutrition/meal-plan/${plan.id}`}
                      >
                        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-brand-300">
                          <p className="font-medium text-gray-900">{plan.name}</p>
                          <p className="mt-1 text-sm text-gray-500">
                            {plan.target_calories} cal/day
                          </p>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            !error && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-white py-16 text-center shadow-sm">
                <Beef className="h-12 w-12 text-gray-300" />
                <p className="mt-4 text-lg font-medium text-gray-900">
                  No meal plan yet
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  Generate a personalized meal plan to get started.
                </p>
              </div>
            )
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
