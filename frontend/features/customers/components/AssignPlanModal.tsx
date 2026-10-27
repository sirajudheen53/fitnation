"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button, Card, CardBody, Spinner } from "@/components/ui";
import { errorMessage, fetchDietPlans, fetchWorkoutPlans } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { DietPlan } from "@/types/diet";
import type { WorkoutPlan } from "@/types/workout";

export type PlanAssignmentKind = "workout" | "diet";

export interface AssignPlanInputs {
  planId: number;
  startDate: string;
  endDate: string;
  notes: string;
  replaceActive: boolean;
}

interface AssignPlanModalProps {
  /** Which catalogue to offer: workout plans or diet (meal) plans. */
  kind: PlanAssignmentKind;
  /** Whether the customer already holds an active assignment of this kind —
   * shows the "replace current" toggle, pre-checked (issue #90). */
  hasActiveAssignment: boolean;
  onSubmit: (inputs: AssignPlanInputs) => Promise<void>;
  onClose: () => void;
}

const KIND_LABELS: Record<PlanAssignmentKind, string> = {
  workout: "workout plan",
  diet: "meal plan",
};

/**
 * Assign-plan dialog (issue #90): pick a plan from the tenant catalogue,
 * optionally set the window (start/end dates) and notes. When the customer
 * already has an active plan of this kind the assignment replaces it
 * (previous plan is kept as history).
 */
export function AssignPlanModal({
  kind,
  hasActiveAssignment,
  onSubmit,
  onClose,
}: AssignPlanModalProps) {
  const [plans, setPlans] = useState<(WorkoutPlan | DietPlan)[] | null>(null);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [planId, setPlanId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [replaceActive, setReplaceActive] = useState(hasActiveAssignment);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const load =
      kind === "workout" ? fetchWorkoutPlans(token) : fetchDietPlans(token);
    load
      .then((response) => setPlans(response.results))
      .catch((err) => setPlansError(errorMessage(err)));
  }, [kind]);

  async function submit() {
    if (!planId) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        planId,
        startDate,
        endDate,
        notes,
        replaceActive,
      });
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              Assign {KIND_LABELS[kind]}
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          {plansError ? (
            <p className="text-sm text-red-600">{plansError}</p>
          ) : plans === null ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : (
            <>
              <div className="space-y-1.5">
                <label htmlFor="assign-plan" className="block text-sm font-medium text-gray-700">
                  Plan
                </label>
                <select
                  id="assign-plan"
                  data-testid="plan-select"
                  value={planId ?? ""}
                  onChange={(e) => setPlanId(e.target.value ? Number(e.target.value) : null)}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">Select a {KIND_LABELS[kind]}…</option>
                  {plans.map((plan) => (
                    <option key={plan.id} value={plan.id}>
                      {plan.name}
                    </option>
                  ))}
                </select>
                {plans.length === 0 && (
                  <p className="text-xs text-gray-500">
                    No {KIND_LABELS[kind]}s yet — create one first.
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label htmlFor="assign-plan-start" className="block text-sm font-medium text-gray-700">
                    Start date
                  </label>
                  <input
                    id="assign-plan-start"
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="assign-plan-end" className="block text-sm font-medium text-gray-700">
                    End date (optional)
                  </label>
                  <input
                    id="assign-plan-end"
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="assign-plan-notes" className="block text-sm font-medium text-gray-700">
                  Notes (optional)
                </label>
                <textarea
                  id="assign-plan-notes"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              {hasActiveAssignment && (
                <label className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={replaceActive}
                    onChange={(e) => setReplaceActive(e.target.checked)}
                    className="mt-0.5 h-4 w-4"
                    aria-label="Replace current assignment"
                  />
                  <span>
                    Replace the current {KIND_LABELS[kind]} — it is deactivated
                    (kept as history) when this one starts.
                  </span>
                </label>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} disabled={submitting}>
                  Cancel
                </Button>
                <Button
                  onClick={submit}
                  disabled={!planId || submitting}
                  loading={submitting}
                  aria-label="Confirm plan assignment"
                >
                  Assign {KIND_LABELS[kind]}
                </Button>
              </div>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
