"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui";
import type { ExerciseCategory, ExerciseFilters } from "@/types/exercise";
import {
  DIFFICULTY_OPTIONS,
  MUSCLE_GROUP_OPTIONS,
  EQUIPMENT_OPTIONS,
} from "./helpers";

interface ExerciseFiltersProps {
  categories: ExerciseCategory[];
  filters: ExerciseFilters;
  onChange: (filters: ExerciseFilters) => void;
}

export function ExerciseFilters({
  categories,
  filters,
  onChange,
}: ExerciseFiltersProps) {
  const update = (patch: Partial<ExerciseFilters>) => {
    onChange({ ...filters, ...patch });
  };

  const hasActiveFilters =
    filters.category ||
    filters.difficulty ||
    filters.muscle_group ||
    filters.equipment_needed ||
    filters.search;

  const clearAll = () => {
    onChange({});
  };

  const selectClass =
    "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

  return (
    <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="flex-1">
          <Input
            label="Search"
            placeholder="Search exercises…"
            icon={<Search className="h-4 w-4" />}
            value={filters.search ?? ""}
            onChange={(e) => update({ search: e.target.value })}
            aria-label="Search exercises"
          />
        </div>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearAll}
            className="inline-flex items-center gap-1.5 self-end rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 md:self-auto"
          >
            <X className="h-4 w-4" /> Clear filters
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1.5">
          <label htmlFor="filter-category" className="block text-sm font-medium text-gray-700">
            Category
          </label>
          <select
            id="filter-category"
            className={selectClass}
            value={filters.category ?? ""}
            onChange={(e) => update({ category: e.target.value || undefined })}
          >
            <option value="">All categories</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="filter-difficulty" className="block text-sm font-medium text-gray-700">
            Difficulty
          </label>
          <select
            id="filter-difficulty"
            className={selectClass}
            value={filters.difficulty ?? ""}
            onChange={(e) => update({ difficulty: e.target.value || undefined })}
          >
            <option value="">All levels</option>
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="filter-muscle" className="block text-sm font-medium text-gray-700">
            Muscle group
          </label>
          <select
            id="filter-muscle"
            className={selectClass}
            value={filters.muscle_group ?? ""}
            onChange={(e) => update({ muscle_group: e.target.value || undefined })}
          >
            <option value="">All muscles</option>
            {MUSCLE_GROUP_OPTIONS.map((group) => (
              <option key={group} value={group}>
                {group
                  .split("_")
                  .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="filter-equipment" className="block text-sm font-medium text-gray-700">
            Equipment
          </label>
          <select
            id="filter-equipment"
            className={selectClass}
            value={filters.equipment_needed ?? ""}
            onChange={(e) => update({ equipment_needed: e.target.value || undefined })}
          >
            <option value="">Any equipment</option>
            {EQUIPMENT_OPTIONS.map((equipment) => (
              <option key={equipment} value={equipment}>
                {equipment
                  .split(" ")
                  .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
