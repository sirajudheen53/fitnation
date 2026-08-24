"use client";

import { formatNumber } from "./nutritionHelpers";

interface MacroBar {
  label: string;
  value: number;
  grams: number;
  color: string;
}

interface NutritionBarsProps {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  /** Optional target calories to scale the bars against. */
  targetCalories?: number;
}

/**
 * Simple CSS-based macro visualization. Renders three horizontal bars
 * (protein / carbs / fat) scaled relative to the calorie target, plus a
 * calorie total. No charting library is used.
 */
export function NutritionBars({
  calories,
  protein,
  carbs,
  fat,
  targetCalories,
}: NutritionBarsProps) {
  const basis = targetCalories && targetCalories > 0 ? targetCalories : calories || 1;

  const macros: MacroBar[] = [
    { label: "Protein", value: protein, grams: protein, color: "bg-blue-500" },
    { label: "Carbs", value: carbs, grams: carbs, color: "bg-amber-500" },
    { label: "Fat", value: fat, grams: fat, color: "bg-rose-500" },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-gray-700">Total calories</span>
        <span className="text-lg font-semibold text-gray-900">
          {formatNumber(calories)} kcal
        </span>
      </div>

      {macros.map((macro) => {
        const pct = Math.min(100, (macro.value / basis) * 100);
        return (
          <div key={macro.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium text-gray-600">{macro.label}</span>
              <span className="text-gray-500">{formatNumber(macro.grams)} g</span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full rounded-full ${macro.color}`}
                style={{ width: `${pct}%` }}
                role="progressbar"
                aria-valuenow={Math.round(pct)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${macro.label} ${formatNumber(macro.grams)} grams`}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
