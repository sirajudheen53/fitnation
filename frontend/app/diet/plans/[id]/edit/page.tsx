"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { DietPlanForm } from "@/features/diet/components/DietPlanForm";
import { Spinner, Alert } from "@/components/ui";
import {
  fetchDietPlan,
  fetchFoodItems,
  updateDietPlan,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { DietPlan, DietPlanFormData, FoodItem } from "@/types/diet";

export default function EditDietPlanPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [plan, setPlan] = useState<DietPlan | null>(null);
  const [foodItems, setFoodItems] = useState<FoodItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/diet/plans/new")) {
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
        const [planData, foodRes] = await Promise.all([
          fetchDietPlan(id, authToken),
          fetchFoodItems(authToken),
        ]);
        setPlan(planData);
        setFoodItems(foodRes.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router, userRole]);

  const handleSubmit = async (data: DietPlanFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await updateDietPlan(id, data, token);
      toast.success("Diet plan updated");
      router.push(`/diet/plans/${id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Edit diet plan">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !plan && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && plan && (
        <DietPlanForm
          plan={plan}
          foodItems={foodItems}
          submitLabel="Save changes"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
