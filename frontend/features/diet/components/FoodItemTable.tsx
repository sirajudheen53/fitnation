"use client";

import { useState } from "react";
import { Search, Leaf, Beef, X } from "lucide-react";
import { Badge, Button, Input } from "@/components/ui";
import type { FoodItem, FoodGroup } from "@/types/diet";
import { FOOD_GROUP_LABELS, formatNumber } from "./nutritionHelpers";

const FOOD_GROUPS = Object.keys(FOOD_GROUP_LABELS) as FoodGroup[];

interface FoodItemTableProps {
  foodItems: FoodItem[];
  loading?: boolean;
  onSearch?: (search: string) => void;
  onFilter?: (foodGroup: string, isVeg: string) => void;
}

export function FoodItemTable({
  foodItems,
  loading = false,
  onSearch,
  onFilter,
}: FoodItemTableProps) {
  const [search, setSearch] = useState("");
  const [foodGroup, setFoodGroup] = useState("");
  const [isVeg, setIsVeg] = useState("");
  const [selected, setSelected] = useState<FoodItem | null>(null);

  const handleSearch = (value: string) => {
    setSearch(value);
    onSearch?.(value);
  };

  const handleGroup = (value: string) => {
    setFoodGroup(value);
    onFilter?.(value, isVeg);
  };

  const handleVeg = (value: string) => {
    setIsVeg(value);
    onFilter?.(foodGroup, value);
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-500">
        Loading food items…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search food items…"
            aria-label="Search food items"
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <select
          value={foodGroup}
          onChange={(e) => handleGroup(e.target.value)}
          aria-label="Filter by food group"
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 md:w-48"
        >
          <option value="">All groups</option>
          {FOOD_GROUPS.map((g) => (
            <option key={g} value={g}>
              {FOOD_GROUP_LABELS[g]}
            </option>
          ))}
        </select>
        <select
          value={isVeg}
          onChange={(e) => handleVeg(e.target.value)}
          aria-label="Filter by veg / non-veg"
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 md:w-40"
        >
          <option value="">All diets</option>
          <option value="true">Veg</option>
          <option value="false">Non-veg</option>
        </select>
      </div>

      {/* Table */}
      {foodItems.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No food items found.</p>
          <p className="mt-1 text-sm text-gray-400">
            Try adjusting your search or filters.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Serving</th>
                <th className="px-6 py-3 font-medium">Calories</th>
                <th className="px-6 py-3 font-medium">Protein</th>
                <th className="px-6 py-3 font-medium">Carbs</th>
                <th className="px-6 py-3 font-medium">Fat</th>
                <th className="px-6 py-3 font-medium">Group</th>
                <th className="px-6 py-3 font-medium">Diet</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {foodItems.map((item) => (
                <tr
                  key={item.id}
                  className="cursor-pointer hover:bg-gray-50"
                  onClick={() => setSelected(item)}
                >
                  <td className="px-6 py-4 font-medium text-gray-900">{item.name}</td>
                  <td className="px-6 py-4 text-gray-600">{item.serving_size}</td>
                  <td className="px-6 py-4 text-gray-700">
                    {formatNumber(item.calories)}
                  </td>
                  <td className="px-6 py-4 text-gray-700">
                    {formatNumber(item.protein)}g
                  </td>
                  <td className="px-6 py-4 text-gray-700">
                    {formatNumber(item.carbs)}g
                  </td>
                  <td className="px-6 py-4 text-gray-700">{formatNumber(item.fat)}g</td>
                  <td className="px-6 py-4 text-gray-600">
                    {FOOD_GROUP_LABELS[item.food_group] ?? item.food_group}
                  </td>
                  <td className="px-6 py-4">
                    {item.is_veg ? (
                      <Badge variant="success">
                        <Leaf className="mr-1 h-3 w-3" /> Veg
                      </Badge>
                    ) : (
                      <Badge variant="danger">
                        <Beef className="mr-1 h-3 w-3" /> Non-veg
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setSelected(null)}
          role="dialog"
          aria-modal="true"
          aria-label={`${selected.name} details`}
        >
          <div
            className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{selected.name}</h3>
                <p className="mt-0.5 text-sm text-gray-500">{selected.serving_size}</p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {selected.is_veg ? (
                <Badge variant="success">Veg</Badge>
              ) : (
                <Badge variant="danger">Non-veg</Badge>
              )}
              <Badge variant="info">
                {FOOD_GROUP_LABELS[selected.food_group] ?? selected.food_group}
              </Badge>
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-4">
              {[
                { label: "Calories", value: `${formatNumber(selected.calories)} kcal` },
                { label: "Protein", value: `${formatNumber(selected.protein)} g` },
                { label: "Carbs", value: `${formatNumber(selected.carbs)} g` },
                { label: "Fat", value: `${formatNumber(selected.fat)} g` },
                { label: "Fiber", value: `${formatNumber(selected.fiber)} g` },
                {
                  label: "Glycemic index",
                  value: selected.glycemic_index != null ? String(selected.glycemic_index) : "—",
                },
              ].map((row) => (
                <div key={row.label} className="rounded-lg bg-gray-50 p-3">
                  <dt className="text-xs text-gray-500">{row.label}</dt>
                  <dd className="mt-0.5 text-sm font-semibold text-gray-900">
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>

            <div className="mt-6 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
