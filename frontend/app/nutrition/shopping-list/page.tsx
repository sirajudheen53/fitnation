"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShoppingBasket, ArrowLeft, Sparkles } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchShoppingList, fetchMealPlans, generateMealPlan, errorMessage } from "@/lib/api";
import type { ShoppingList } from "@/types/nutrition";

export default function ShoppingListPage() {
  const router = useRouter();
  const [lists, setLists] = useState<ShoppingList[]>([]);
  const [activeList, setActiveList] = useState<ShoppingList | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLists = () => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/nutrition/shopping-list");
      return;
    }
    fetchShoppingList(token)
      .then((data) => {
        setLists(data.results);
        setActiveList(data.results[0] ?? null);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadLists();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGenerate = async () => {
    const token = getToken();
    if (!token) return;
    setGenerating(true);
    setError(null);
    try {
      const plans = await fetchMealPlans(token);
      const plan = plans.results[0];
      if (!plan) {
        setError("Generate a meal plan first.");
        return;
      }
      await generateMealPlan(token, {
        target_calories: plan.target_calories,
        cuisine: plan.cuisine ?? undefined,
      });
      loadLists();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const toggleItem = (itemId: number) => {
    setActiveList((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.map((it) =>
              it.id === itemId ? { ...it, checked: !it.checked } : it,
            ),
          }
        : prev,
    );
  };

  return (
    <DashboardLayout
      title="Shopping List"
      actions={
        <Button variant="outline" size="sm" onClick={handleGenerate} disabled={generating}>
          <Sparkles className="mr-1 h-4 w-4" />
          {generating ? "Generating..." : "Generate from meal plan"}
        </Button>
      }
    >
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error && lists.length === 0 ? (
        <Alert variant="error">{error}</Alert>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* List selector */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-4 py-3">
              <h3 className="font-semibold text-gray-900">Lists</h3>
            </div>
            {lists.length === 0 ? (
              <p className="px-4 py-6 text-sm text-gray-500">
                No shopping lists yet.
              </p>
            ) : (
              lists.map((list) => (
                <button
                  key={list.id}
                  type="button"
                  onClick={() => setActiveList(list)}
                  className={`block w-full px-4 py-3 text-left text-sm hover:bg-gray-50 ${
                    activeList?.id === list.id
                      ? "bg-brand-50 text-brand-700"
                      : "text-gray-700"
                  }`}
                >
                  <span className="font-medium">{list.name}</span>
                  <span className="block text-xs text-gray-400">
                    {list.items.length} items
                  </span>
                </button>
              ))
            )}
          </div>

          {/* Items */}
          <div className="md:col-span-3 rounded-xl border border-gray-200 bg-white shadow-sm">
            {activeList ? (
              <>
                <div className="border-b border-gray-100 px-6 py-4">
                  <h3 className="font-semibold text-gray-900">
                    {activeList.name}
                  </h3>
                </div>
                <div className="divide-y divide-gray-100">
                  {activeList.items.length === 0 ? (
                    <p className="px-6 py-10 text-center text-sm text-gray-500">
                      No items in this list.
                    </p>
                  ) : (
                    activeList.items.map((item) => (
                      <label
                        key={item.id}
                        className="flex cursor-pointer items-center gap-3 px-6 py-3 hover:bg-gray-50"
                      >
                        <input
                          type="checkbox"
                          checked={item.checked}
                          onChange={() => toggleItem(item.id)}
                          className="h-4 w-4 rounded border-gray-300 text-brand-600"
                        />
                        <div className="flex-1">
                          <p
                            className={`font-medium ${
                              item.checked
                                ? "text-gray-400 line-through"
                                : "text-gray-900"
                            }`}
                          >
                            {item.name}
                          </p>
                          {item.category && (
                            <span className="text-xs text-gray-400">
                              {item.category}
                            </span>
                          )}
                        </div>
                        <span className="text-sm text-gray-500">
                          {item.quantity}
                        </span>
                      </label>
                    ))
                  )}
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <ShoppingBasket className="h-12 w-12 text-gray-300" />
                <p className="mt-4 text-lg font-medium text-gray-900">
                  Select a list
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  Choose a shopping list from the sidebar or generate one.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
