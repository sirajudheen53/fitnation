"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Target, Pencil, CheckCircle2, XCircle } from "lucide-react";
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
  target_value: z.coerce
    .number()
    .positive()
    .optional()
    .or(z.nan().transform(() => undefined)),
  target_unit: z.string().max(50).optional().or(z.literal("")),
  target_date: z.string().optional().or(z.literal("")),
  current_value: z.coerce
    .number()
    .nonnegative()
    .optional()
    .or(z.nan().transform(() => undefined)),
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

const STATUS_OPTIONS: FitnessGoalStatus[] = ["active", "achieved", "abandoned"];

interface FitnessGoalsTabProps {
  goals: CustomerFitnessGoal[];
  loading?: boolean;
  saving?: boolean;
  error?: unknown;
  onAdd: (data: FitnessGoalFormData) => void | Promise<void>;
  /** Called when user updates current_value or status of an existing goal. */
  onUpdate?: (
    goalId: number,
    data: Partial<FitnessGoalFormData>,
  ) => void | Promise<void>;
}

export function FitnessGoalsTab({
  goals,
  loading = false,
  saving = false,
  error,
  onAdd,
  onUpdate,
}: FitnessGoalsTabProps) {
  const [showForm, setShowForm] = useState(false);
  const [editGoalId, setEditGoalId] = useState<number | null>(null);
  const [updatingGoalId, setUpdatingGoalId] = useState<number | null>(null);

  const {
    register: registerAdd,
    handleSubmit: handleAddSubmit,
    reset: resetAdd,
    formState: { errors: addErrors },
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

  const {
    register: registerEdit,
    handleSubmit: handleEditSubmit,
    reset: resetEdit,
    setValue: setEditValue,
    watch: watchEdit,
    formState: { errors: editErrors },
  } = useForm<GoalSchemaData>({
    resolver: zodResolver(goalSchema),
  });

  const handleAdd = async (data: GoalSchemaData) => {
    await onAdd({
      goal_type: data.goal_type,
      target_value: data.target_value,
      target_unit: data.target_unit || undefined,
      target_date: data.target_date || undefined,
      current_value: data.current_value,
    });
    resetAdd();
    setShowForm(false);
  };

  /** Open the inline edit form for a goal. */
  const startEdit = (goal: CustomerFitnessGoal) => {
    setEditGoalId(goal.id);
    resetEdit({
      goal_type: goal.goal_type,
      target_value: goal.target_value != null ? Number(goal.target_value) : undefined,
      target_unit: goal.target_unit || "",
      target_date: goal.target_date || "",
      current_value: goal.current_value != null ? Number(goal.current_value) : undefined,
    });
  };

  /** Save inline edits (current_value / status). */
  const handleSaveEdit = async (goalId: number, data: GoalSchemaData) => {
    if (onUpdate) {
      await onUpdate(goalId, {
        current_value: data.current_value,
        target_value: data.target_value,
        target_unit: data.target_unit || undefined,
        target_date: data.target_date || undefined,
      });
    }
    setEditGoalId(null);
  };

  /** Quick status change (achieve / abandon). */
  const handleStatusChange = async (goalId: number, newStatus: FitnessGoalStatus) => {
    if (!onUpdate) return;
    setUpdatingGoalId(goalId);
    try {
      await onUpdate(goalId, { status: newStatus });
    } finally {
      setUpdatingGoalId(null);
    }
  };

  const isBusy = saving || updatingGoalId !== null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Fitness goals</h3>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowForm((v) => !v)}
        >
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

      {/* Goal list */}
      {!loading && goals.length > 0 && (
        <div className="space-y-3">
          {goals.map((goal) => {
            const meta = getGoalStatusMeta(goal.status);
            const progress = clampProgress(goal.progress_percentage);
            const isEditing = editGoalId === goal.id;
            const isUpdating = updatingGoalId === goal.id;
            const editValues = watchEdit();

            return (
              <div
                key={goal.id}
                className="rounded-xl border border-gray-200 bg-white p-4"
              >
                {/* Header row */}
                <div className="mb-2 flex items-center justify-between">
                  <p className="font-medium text-gray-900">
                    {getFitnessGoalLabel(goal.goal_type)}
                  </p>
                  <div className="flex items-center gap-2">
                    <Badge variant={meta.variant}>{meta.label}</Badge>
                    {onUpdate && goal.status === "active" && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleStatusChange(goal.id, "achieved")}
                          disabled={isBusy}
                          title="Mark as achieved"
                          className="flex h-6 w-6 items-center justify-center rounded text-green-600 hover:bg-green-50 disabled:opacity-40"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleStatusChange(goal.id, "abandoned")}
                          disabled={isBusy}
                          title="Mark as abandoned"
                          className="flex h-6 w-6 items-center justify-center rounded text-red-500 hover:bg-red-50 disabled:opacity-40"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Progress bar — clickable to edit current value */}
                {isEditing ? null : (
                  <button
                    type="button"
                    onClick={() => onUpdate && startEdit(goal)}
                    className="mb-2 flex w-full flex-col gap-1 text-left focus:outline-none"
                    disabled={!onUpdate}
                    title={onUpdate ? "Click to update progress" : undefined}
                  >
                    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                      <div
                        className="h-full rounded-full bg-brand-600 transition-all"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </button>
                )}

                {/* Inline edit form */}
                {isEditing ? (
                  <form
                    onSubmit={handleEditSubmit((data) =>
                      handleSaveEdit(goal.id, data),
                    )}
                    className="space-y-3 rounded-lg bg-gray-50 p-3"
                  >
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Input
                        label="Current"
                        type="number"
                        placeholder="e.g. 72"
                        error={editErrors.current_value?.message}
                        {...registerEdit("current_value")}
                      />
                      <Input
                        label="Target"
                        type="number"
                        placeholder="e.g. 70"
                        error={editErrors.target_value?.message}
                        {...registerEdit("target_value")}
                      />
                      <Input
                        label="Unit"
                        placeholder="kg"
                        {...registerEdit("target_unit")}
                      />
                      <Input
                        label="Target date"
                        type="date"
                        error={editErrors.target_date?.message}
                        {...registerEdit("target_date")}
                      />
                    </div>
                    {/* Status selector */}
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`edit-status-${goal.id}`}
                        className="block text-sm font-medium text-gray-700"
                      >
                        Status
                      </label>
                      <select
                        id={`edit-status-${goal.id}`}
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                        value={editValues?.goal_type ?? goal.goal_type}
                        {...registerEdit("goal_type")}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {getGoalStatusMeta(s).label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        type="submit"
                        size="sm"
                        loading={isUpdating && updatingGoalId === goal.id}
                      >
                        Save
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setEditGoalId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </form>
                ) : (
                  /* Stats row */
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>
                      {goal.current_value != null ? goal.current_value : "—"}
                      {goal.target_unit ? ` ${goal.target_unit}` : ""}{" "}
                      /{" "}
                      {goal.target_value != null ? goal.target_value : "—"}
                      {goal.target_unit ? ` ${goal.target_unit}` : ""}
                    </span>
                    <div className="flex items-center gap-2">
                      {onUpdate && (
                        <button
                          type="button"
                          onClick={() => startEdit(goal)}
                          className="flex items-center gap-1 text-brand-600 hover:text-brand-700"
                          title="Edit goal"
                        >
                          <Pencil className="h-3 w-3" />
                          Edit
                        </button>
                      )}
                      <span>
                        {goal.progress_percentage != null
                          ? `${Math.round(progress)}%`
                          : "—"}
                      </span>
                    </div>
                  </div>
                )}

                {goal.target_date && !isEditing && (
                  <p className="mt-1 text-xs text-gray-400">
                    Target: {goal.target_date}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add goal form */}
      {!loading && showForm && (
        <form
          onSubmit={handleAddSubmit(handleAdd)}
          className="space-y-4 rounded-xl border border-gray-200 bg-white p-4"
        >
          <div className="space-y-1.5">
            <label htmlFor="goal_type" className="block text-sm font-medium text-gray-700">
              Goal type
            </label>
            <select
              id="goal_type"
              {...registerAdd("goal_type")}
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
              error={addErrors.target_value?.message}
              {...registerAdd("target_value")}
            />
            <Input
              label="Unit"
              placeholder="kg"
              error={addErrors.target_unit?.message}
              {...registerAdd("target_unit")}
            />
            <Input
              label="Target date"
              type="date"
              error={addErrors.target_date?.message}
              {...registerAdd("target_date")}
            />
          </div>
          <Input
            label="Current value (optional)"
            type="number"
            placeholder="e.g. 80"
            error={addErrors.current_value?.message}
            {...registerAdd("current_value")}
          />

          <Button type="submit" loading={saving}>
            Add goal
          </Button>
        </form>
      )}
    </div>
  );
}
