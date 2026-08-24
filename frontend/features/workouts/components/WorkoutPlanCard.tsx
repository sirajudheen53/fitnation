"use client";

import Link from "next/link";
import { Pencil, Eye, Copy } from "lucide-react";
import { Badge } from "@/components/ui";
import type { WorkoutDifficulty, WorkoutGoal, WorkoutPlan } from "@/types/workout";
import {
  DIFFICULTY_LABELS,
  GOAL_LABELS,
  difficultyBadgeVariant,
  goalBadgeVariant,
} from "./helpers";

interface WorkoutPlanCardProps {
  plan: WorkoutPlan;
  canEdit?: boolean;
  onDuplicate?: (plan: WorkoutPlan) => void;
}

export function WorkoutPlanCard({ plan, canEdit = false, onDuplicate }: WorkoutPlanCardProps) {
  const dayCount = plan.days?.length ?? 0;
  return (
    <div className="flex flex-col justify-between rounded-xl border border-gray-200 p-5">
      <div>
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold text-gray-900">{plan.name}</h3>
          <Badge variant={goalBadgeVariant(plan.goal)}>{GOAL_LABELS[plan.goal]}</Badge>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge variant={difficultyBadgeVariant(plan.difficulty)}>
            {DIFFICULTY_LABELS[plan.difficulty]}
          </Badge>
          {plan.is_template ? (
            <Badge variant="info">Template</Badge>
          ) : (
            <Badge variant="success">Active</Badge>
          )}
          <Badge variant="default">{plan.duration_weeks} weeks</Badge>
          <Badge variant="default">{dayCount} days</Badge>
        </div>
        {plan.description && (
          <p className="mt-2 text-sm text-gray-600">{plan.description}</p>
        )}
      </div>
      <div className="mt-4 flex items-center gap-2">
        <Link
          href={`/workouts/plans/${plan.id}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-700"
        >
          <Eye className="h-4 w-4" /> View
        </Link>
        {canEdit && (
          <Link
            href={`/workouts/plans/${plan.id}/edit`}
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
