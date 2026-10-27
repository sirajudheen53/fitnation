"use client";

import { useCallback, useEffect, useState } from "react";
import { Dumbbell, Utensils } from "lucide-react";
import { toast } from "sonner";
import { Button, Card, CardBody, CardHeader, Spinner } from "@/components/ui";
import {
  assignDietPlan,
  assignWorkoutPlan,
  errorMessage,
  fetchActiveDietAssignments,
  fetchActiveWorkoutAssignments,
  unassignDietAssignment,
  unassignWorkoutAssignment,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import {
  AssignPlanModal,
  type AssignPlanInputs,
  type PlanAssignmentKind,
} from "@/features/customers/components/AssignPlanModal";
import type { Customer } from "@/types/customer";
import type { DietAssignment } from "@/types/diet";
import type { WorkoutAssignment } from "@/types/workout";

interface PlanAssignmentsSectionProps {
  customer: Customer;
}

interface UnassignTarget {
  kind: PlanAssignmentKind;
  assignmentId: number;
  planName: string;
}

const KIND_LABELS: Record<PlanAssignmentKind, string> = {
  workout: "Workout plan",
  diet: "Meal plan",
};

/**
 * Customer detail → Plans section (issue #90): the current workout and meal
 * plan assignments with assign / replace / unassign actions. Unassigning
 * deactivates the assignment (kept as history); assigning with "replace"
 * ends the previous plan the day the new one starts.
 */
export function PlanAssignmentsSection({ customer }: PlanAssignmentsSectionProps) {
  const [workoutAssignment, setWorkoutAssignment] = useState<WorkoutAssignment | null>(null);
  const [dietAssignment, setDietAssignment] = useState<DietAssignment | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [assignKind, setAssignKind] = useState<PlanAssignmentKind | null>(null);
  const [unassignTarget, setUnassignTarget] = useState<UnassignTarget | null>(null);
  const [unassigning, setUnassigning] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    Promise.all([
      fetchActiveWorkoutAssignments(token, customer.id),
      fetchActiveDietAssignments(token, customer.id),
    ])
      .then(([workout, diet]) => {
        if (cancelled) return;
        setWorkoutAssignment(workout[0] ?? null);
        setDietAssignment(diet[0] ?? null);
        setLoadError(null);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [customer.id, refreshKey]);

  /** Re-read both assignments after a mutation. */
  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  /** Assign (or replace) the plan of `kind`, then refresh both rows. */
  async function handleAssign(kind: PlanAssignmentKind, inputs: AssignPlanInputs) {
    const token = getToken();
    if (!token) return;
    setAssignKind(null);
    const common = {
      customer: customer.id,
      start_date: inputs.startDate,
      ...(inputs.endDate ? { end_date: inputs.endDate } : {}),
      ...(inputs.notes ? { notes: inputs.notes } : {}),
      replace_active: inputs.replaceActive,
    };
    try {
      if (kind === "workout") {
        await assignWorkoutPlan({ ...common, workout_plan: inputs.planId }, token);
      } else {
        await assignDietPlan({ ...common, diet_plan: inputs.planId }, token);
      }
      refresh();
      toast.success(
        `${KIND_LABELS[kind]} assigned to ${customer.name}${inputs.replaceActive ? " (previous plan archived)" : ""}`,
      );
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function handleUnassign(target: UnassignTarget) {
    const token = getToken();
    if (!token) return;
    setUnassigning(true);
    try {
      if (target.kind === "workout") {
        await unassignWorkoutAssignment(target.assignmentId, token);
      } else {
        await unassignDietAssignment(target.assignmentId, token);
      }
      refresh();
      toast.success(`${target.planName} unassigned from ${customer.name}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setUnassigning(false);
      setUnassignTarget(null);
    }
  }

  function renderRow(kind: PlanAssignmentKind) {
    const assignment =
      kind === "workout" ? workoutAssignment : dietAssignment;
    const planName =
      kind === "workout"
        ? (workoutAssignment?.workout_plan_name ?? "")
        : (dietAssignment?.diet_plan_name ?? "");
    return (
      <div
        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 p-3"
        data-testid={`${kind}-plan-row`}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-brand-700">
            {kind === "workout" ? (
              <Dumbbell className="h-5 w-5" />
            ) : (
              <Utensils className="h-5 w-5" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {assignment ? planName : `No ${KIND_LABELS[kind].toLowerCase()} assigned`}
            </p>
            {assignment && (
              <p className="text-xs text-gray-500" data-testid={`${kind}-plan-dates`}>
                From {assignment.start_date}
                {assignment.end_date ? ` until ${assignment.end_date}` : " · ongoing"}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {assignment && (
            <Button
              variant="ghost"
              size="sm"
              className="text-red-600 hover:bg-red-50"
              onClick={() =>
                setUnassignTarget({ kind, assignmentId: assignment.id, planName })
              }
              aria-label={`Unassign ${planName}`}
            >
              Unassign
            </Button>
          )}
          <Button size="sm" variant={assignment ? "outline" : "primary"} onClick={() => setAssignKind(kind)}>
            {assignment ? "Change" : "Assign"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Card data-testid="plan-assignments-section">
      <CardHeader>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Dumbbell className="h-5 w-5 text-brand-600" />
          Plans
        </h2>
        <p className="text-sm text-gray-500">
          Current workout and meal plan assignments. Replacing a plan keeps the
          previous one as history.
        </p>
      </CardHeader>
      <CardBody className="space-y-3">
        {!loaded && !loadError && (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        )}
        {loadError && <p className="text-sm text-red-600">{loadError}</p>}
        {loaded && !loadError && renderRow("workout")}
        {loaded && !loadError && renderRow("diet")}
      </CardBody>

      {assignKind && (
        <AssignPlanModal
          kind={assignKind}
          hasActiveAssignment={
            (assignKind === "workout" ? workoutAssignment : dietAssignment) !== null
          }
          onSubmit={(inputs) => handleAssign(assignKind, inputs)}
          onClose={() => setAssignKind(null)}
        />
      )}

      {unassignTarget && (
        <ConfirmDialog
          title={`Unassign ${KIND_LABELS[unassignTarget.kind].toLowerCase()}?`}
          destructive
          busy={unassigning}
          confirmLabel="Unassign"
          onConfirm={() => handleUnassign(unassignTarget)}
          onClose={() => setUnassignTarget(null)}
        >
          <p>
            {unassignTarget.planName} will no longer be active for {customer.name}. The
            assignment is kept as history — you can assign a plan again anytime.
          </p>
        </ConfirmDialog>
      )}
    </Card>
  );
}
