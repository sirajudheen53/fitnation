"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Target } from "lucide-react";
import { Button, Input, Alert, Badge } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type {
  CustomerFitnessGoal,
  FitnessGoalFormData,
  FitnessGoalStatus,
  FitnessGoalType,
} from "@/types/customer-detail";
import { getFitnessGoalLabel } from "@/types/customer-detail";

/** Clamp a progress percentage to 0–100 for the progress bar. */
export function clampProgress(value: number | null | undefined): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

/** Return badge metadata for a goal status. */
export function getGoalStatusMeta(status: FitnessGoalStatus): {
  label: string;
  variant: "success" | "danger" | "default";
} {
  switch (status) {
    case "active":
      return { label: "Active", variant: "success" };
    case "achieved":
      return { label: "Achieved", variant: "default" };
    case "abandoned":
      return { label: "Abandoned", variant: "danger" };
    default:
      return { label: status, variant: "default" };
  }
}

const goalSchema = z.object({
  goal_type: z.enum([
    "lose_weight",
    "build_muscle",
    "endurance",
    "flexibility",
    "general_fitness",
    "sport_specific",
    "other",
  ]),
  target_value: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  target_unit: z.string().max(50).optional().or(z.literal("")),
  target_date: z.string().optional().or(z.literal("")),
  current_value: z.coerce.number().nonnegative().optional().or(z.nan().transform(() => undefined)),
});

type GoalSchemaData = z.infer<typeof goalSchema>;

const GOAL_TYPE_OPTIONS: FitnessGoalType[] = [
  "lose_weight",
  "build_muscle",
  "endurance",
  "flexibility",
  "general_fitness",
  "sport_specific",
  "other",
];

interface FitnessGoalsTabProps {
  goals: CustomerFitnessGoal[];
  loading?: boolean;
  saving?: boolean;
  error?: unknown;
  onAdd: (data: FitnessGoalFormData) => void | Promise<void>;
}

export function FitnessGoalsTab({
  goals,
  loading = false,
  saving = false,
  error,
  onAdd,
}: FitnessGoalsTabProps) {
  const [showForm, setShowForm] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GoalSchemaData>({
    resolver: zodResolver(goalSchema),
    defaultValues: {
      goal_type: "general_fitness",
      target_value: undefined,
      target_unit: "",
      target_date: "",
      current_value: undefined,
    },
  });

  const handleAdd = async (data: GoalSchemaData) => {
    await onAdd({
      goal_type: data.goal_type,
      target_value: data.target_value,
      target_unit: data.target_unit || undefined,
      target_date: data.target_date || undefined,
      current_value: data.current_value,
    });
    reset();
    setShowForm(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Fitness goals</h3>
        <Button size="sm" variant="outline" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" /> {showForm ? "Cancel" : "Add goal"}
        </Button>
      </div>

      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {loading && <p className="text-sm text-gray-500">Loading goals…</p>}

      {!loading && !showForm && goals.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
          <Target className="mx-auto mb-2 h-6 w-6 text-gray-300" />
          <p className="text-sm text-gray-500">No fitness goals set yet.</p>
        </div>
      )}

      {!loading && goals.length > 0 && (
        <div className="space-y-3">
          {goals.map((goal) => {
            const meta = getGoalStatusMeta(goal.status);
            const progress = clampProgress(goal.progress_percentage);
            return (
              <div key={goal.id} className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="mb-2 flex items-center justify-between">
                  <p className="font-medium text-gray-900">
                    {getFitnessGoalLabel(goal.goal_type)}
                  </p>
                  <Badge variant={meta.variant}>{meta.label}</Badge>
                </div>
                <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-brand-600 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>
                    {goal.current_value != null ? goal.current_value : "—"}
                    {goal.target_unit ? ` ${goal.target_unit}` : ""} /{" "}
                    {goal.target_value != null ? goal.target_value : "—"}
                    {goal.target_unit ? ` ${goal.target_unit}` : ""}
                  </span>
                  <span>{goal.progress_percentage != null ? `${Math.round(progress)}%` : "—"}</span>
                </div>
                {goal.target_date && (
                  <p className="mt-1 text-xs text-gray-400">Target: {goal.target_date}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!loading && showForm && (
        <form
          onSubmit={handleSubmit(handleAdd)}
          className="space-y-4 rounded-xl border border-gray-200 bg-white p-4"
        >
          <div className="space-y-1.5">
            <label htmlFor="goal_type" className="block text-sm font-medium text-gray-700">
              Goal type
            </label>
            <select
              id="goal_type"
              {...register("goal_type")}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
            >
              {GOAL_TYPE_OPTIONS.map((type) => (
                <option key={type} value={type}>
                  {getFitnessGoalLabel(type)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Input
              label="Target value"
              type="number"
              placeholder="e.g. 70"
              error={errors.target_value?.message}
              {...register("target_value")}
            />
            <Input
              label="Unit"
              placeholder="kg"
              error={errors.target_unit?.message}
              {...register("target_unit")}
            />
            <Input
              label="Target date"
              type="date"
              error={errors.target_date?.message}
              {...register("target_date")}
            />
          </div>
          <Input
            label="Current value (optional)"
            type="number"
            placeholder="e.g. 80"
            error={errors.current_value?.message}
            {...register("current_value")}
          />

          <Button type="submit" loading={saving}>
            Add goal
          </Button>
        </form>
      )}
    </div>
  );
}
