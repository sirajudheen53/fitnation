"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { DietPlanForm } from "@/features/diet/components/DietPlanForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchFoodItems, createDietPlan, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { DietPlanFormData, FoodItem } from "@/types/diet";

export default function NewDietPlanPage() {
  const router = useRouter();
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
      router.replace("/login?next=/diet/plans/new");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchFoodItems(authToken);
        setFoodItems(response.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const handleSubmit = async (data: DietPlanFormData) => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/diet/plans/new");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createDietPlan(data, token);
      toast.success("Diet plan created");
      router.push("/diet");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="New diet plan">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && foodItems.length === 0 && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && (
        <DietPlanForm
          foodItems={foodItems}
          submitLabel="Create plan"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
