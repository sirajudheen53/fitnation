"use client";

import Link from "next/link";
import { Pencil, Eye, Copy } from "lucide-react";
import { Badge } from "@/components/ui";
import type { DietPlan, DietGoal } from "@/types/diet";
import { GOAL_LABELS, formatNumber } from "./nutritionHelpers";

const GOAL_VARIANTS: Record<DietGoal, "info" | "warning" | "success"> = {
  bulk: "info",
  cut: "warning",
  maintain: "success",
};

interface DietPlanCardProps {
  plan: DietPlan;
  canEdit?: boolean;
  onDuplicate?: (plan: DietPlan) => void;
}

export function DietPlanCard({ plan, canEdit = false, onDuplicate }: DietPlanCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-xl border border-gray-200 p-5">
      <div>
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold text-gray-900">{plan.name}</h3>
          <Badge variant={GOAL_VARIANTS[plan.goal]}>{GOAL_LABELS[plan.goal]}</Badge>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {plan.is_template ? (
            <Badge variant="info">Template</Badge>
          ) : (
            <Badge variant="success">Active</Badge>
          )}
          <Badge variant="default">{plan.duration_days} days</Badge>
        </div>
        <p className="mt-3 text-lg font-semibold text-brand-600">
          {formatNumber(plan.daily_calories)} kcal/day
        </p>
        <p className="mt-1 text-xs text-gray-500">
          P {formatNumber(plan.protein_ratio)}% · C {formatNumber(plan.carb_ratio)}% · F{" "}
          {formatNumber(plan.fat_ratio)}%
        </p>
        {plan.description && (
          <p className="mt-2 text-sm text-gray-600">{plan.description}</p>
        )}
      </div>
      <div className="mt-4 flex items-center gap-2">
        <Link
          href={`/diet/plans/${plan.id}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-700"
        >
          <Eye className="h-4 w-4" /> View
        </Link>
        {canEdit && (
          <Link
            href={`/diet/plans/${plan.id}/edit`}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Edit plan"
          >
            <Pencil className="h-4 w-4" />
          </Link>
        )}
        {onDuplicate && (
          <button
            onClick={() => onDuplicate(plan)}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Duplicate plan"
          >
            <Copy className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
