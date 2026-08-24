"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { FoodItemTable } from "@/features/diet/components/FoodItemTable";
import { Alert, Spinner } from "@/components/ui";
import { fetchFoodItems, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { FoodItem } from "@/types/diet";

export default function FoodItemsPage() {
  const router = useRouter();
  const [foodItems, setFoodItems] = useState<FoodItem[]>([]);
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
      router.replace("/login?next=/diet/food-items");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchFoodItems(authToken);
        setFoodItems(response.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const handleSearch = async (search: string) => {
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetchFoodItems(token, { search: search || undefined });
      setFoodItems(response.results);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleFilter = async (foodGroup: string, isVeg: string) => {
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetchFoodItems(token, {
        food_group: foodGroup || undefined,
        is_veg: isVeg || undefined,
      });
      setFoodItems(response.results);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <DashboardLayout title="Food database">
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <FoodItemTable
          foodItems={foodItems}
          onSearch={handleSearch}
          onFilter={handleFilter}
        />
      )}
    </DashboardLayout>
  );
}
