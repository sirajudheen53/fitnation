"use client";

import { useEffect, useState } from "react";
import { Check, Smartphone } from "lucide-react";
import { Alert, Button } from "@/components/ui";
import type { MembershipPlan, MembershipPlanType } from "@/types/membership";
import { DESK_PAYMENT_METHODS, isFreeTrial } from "../lib/wizard";
import {
  computeDefaultWindow,
  daysBetween,
  formatDateLong,
  todayISO,
} from "../lib/validity";
import type { OnboardingFormState } from "../lib/wizard";

interface StepPlanPaymentProps {
  state: OnboardingFormState;
  plans: MembershipPlan[];
  loading: boolean;
  onChange: (patch: Partial<OnboardingFormState>) => void;
  onBack: () => void;
  onNext: () => void;
}

const PLAN_TYPE_GROUP_LABELS: Record<MembershipPlanType, string> = {
  monthly: "Monthly",
  quarterly: "Quarterly",
  half_yearly: "Half-yearly",
  yearly: "Yearly",
  pt: "Personal Training",
  trial: "Trial",
};

const GROUP_ORDER: MembershipPlanType[] = [
  "monthly",
  "quarterly",
  "half_yearly",
  "yearly",
  "pt",
  "trial",
];

export function StepPlanPayment({
  state,
  plans,
  loading,
  onChange,
  onBack,
  onNext,
}: StepPlanPaymentProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const plan = plans.find((p) => p.id === state.planId) ?? null;
  const freeTrial = isFreeTrial(plan);

  // Selecting a plan prefills the validity window and the amount (once —
  // a hand-edited end date or amount is never silently overwritten).
  useEffect(() => {
    if (!plan) return;
    const patch: Partial<OnboardingFormState> = {};
    if (state.startDate === "" && !state.endDateOverridden) {
      const window = computeDefaultWindow(plan.duration_days, todayISO());
      patch.startDate = window.start_date;
      patch.endDate = window.end_date;
    } else if (!state.endDateOverridden) {
      patch.endDate = computeDefaultWindow(plan.duration_days, state.startDate).end_date;
    }
    if (state.amount === "") patch.amount = String(Number(plan.price));
    if (Object.keys(patch).length > 0) onChange(patch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.planId]);

  const selectPlan = (selected: MembershipPlan) => {
    const window = computeDefaultWindow(selected.duration_days, state.startDate || todayISO());
    onChange({
      planId: selected.id,
      startDate: window.start_date,
      endDate: window.end_date,
      endDateOverridden: false,
      amount: String(Number(selected.price)),
      // A free trial hides the payment block; anything else resets the method.
      paymentMethod: isFreeTrial(selected) ? null : state.paymentMethod,
    });
  };

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (state.planId === null) next.planId = "Pick a plan to continue";
    if (state.startDate === "") next.startDate = "Start date is required";
    if (state.endDate === "") {
      next.endDate = "End date is required";
    } else if (
      state.startDate !== "" &&
      daysBetween(state.startDate, state.endDate) <= 0
    ) {
      next.endDate = "End date must be after the start date";
    }
    if (!freeTrial && state.paymentMethod === null) {
      next.paymentMethod = "Choose a payment method";
    }
    if (!freeTrial && state.paymentMethod !== null && state.paymentMethod !== "razorpay") {
      if (state.amount === "" || Number(state.amount) < 0) {
        next.amount = "Enter the amount collected";
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const grouped = GROUP_ORDER.map((type) => ({
    type,
    label: PLAN_TYPE_GROUP_LABELS[type],
    plans: plans.filter((p) => p.plan_type === type),
  })).filter((group) => group.plans.length > 0);

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center" data-testid="step-plan-loading">
        <div className="text-sm text-gray-500">Loading plans…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="step-plan-payment">
      {plans.length === 0 && (
        <Alert variant="warning">
          No active plans found — create a plan under Memberships first.
        </Alert>
      )}

      {grouped.map((group) => (
        <div key={group.type}>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            {group.label}
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {group.plans.map((candidate) => {
              const selected = candidate.id === state.planId;
              const trial = candidate.plan_type === "trial";
              return (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => selectPlan(candidate)}
                  aria-pressed={selected}
                  className={`relative rounded-xl border p-4 text-left transition-colors ${
                    selected
                      ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600"
                      : trial
                        ? "border-amber-300 bg-amber-50/50 hover:border-amber-400"
                        : "border-gray-200 bg-white hover:border-gray-300"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-gray-900">{candidate.name}</div>
                      <div className="text-sm text-gray-500">
                        {trial
                          ? `${candidate.duration_days}-day trial`
                          : `${candidate.duration_days} days`}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-brand-600">
                        ₹{Number(candidate.price).toLocaleString()}
                      </div>
                      {selected && (
                        <Check className="ml-auto mt-1 h-4 w-4 text-brand-600" aria-label="Selected" />
                      )}
                    </div>
                  </div>
                  {candidate.includes_app_access && (
                    <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                      <Smartphone className="h-3 w-3" /> App included
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {errors.planId && <p className="mt-2 text-sm text-red-600">{errors.planId}</p>}
        </div>
      ))}

      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-900">Membership validity</h3>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="onboarding-start" className="block text-sm font-medium text-gray-700">
              Start date
            </label>
            <input
              id="onboarding-start"
              type="date"
              value={state.startDate}
              onChange={(e) => {
                const start = e.target.value;
                const patch: Partial<OnboardingFormState> = { startDate: start };
                if (!state.endDateOverridden && plan) {
                  patch.endDate = computeDefaultWindow(plan.duration_days, start).end_date;
                }
                onChange(patch);
              }}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            {errors.startDate && <p className="text-sm text-red-600">{errors.startDate}</p>}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="onboarding-end" className="block text-sm font-medium text-gray-700">
              End date (editable)
            </label>
            <input
              id="onboarding-end"
              type="date"
              value={state.endDate}
              onChange={(e) => onChange({ endDate: e.target.value, endDateOverridden: true })}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            {errors.endDate && <p className="text-sm text-red-600">{errors.endDate}</p>}
          </div>
        </div>
        {state.startDate !== "" && state.endDate !== "" && (
          <p className="mt-3 text-sm text-gray-600" data-testid="validity-summary">
            Membership valid {formatDateLong(state.startDate)} → {formatDateLong(state.endDate)} (
            {daysBetween(state.startDate, state.endDate)} days)
          </p>
        )}
      </div>

      {freeTrial ? (
        <Alert variant="info" data-testid="trial-no-payment">
          Free trial — no payment needed.
        </Alert>
      ) : (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-gray-900">Payment</h3>
          <div className="mt-3">
            <div className="flex flex-wrap overflow-hidden rounded-lg border border-gray-300">
              {DESK_PAYMENT_METHODS.map((method) => (
                <button
                  key={method.value}
                  type="button"
                  onClick={() => onChange({ paymentMethod: method.value })}
                  className={`flex-1 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors ${
                    state.paymentMethod === method.value
                      ? "bg-brand-600 text-white"
                      : "bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {method.label}
                </button>
              ))}
            </div>
            {errors.paymentMethod && (
              <p className="mt-2 text-sm text-red-600">{errors.paymentMethod}</p>
            )}
            {state.paymentMethod === "razorpay" && (
              <p className="mt-2 text-sm text-gray-500">
                The checkout opens after you submit — the membership activates once the
                payment is captured.
              </p>
            )}
          </div>

          {state.paymentMethod !== null && state.paymentMethod !== "razorpay" && (
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="onboarding-amount" className="block text-sm font-medium text-gray-700">
                  Amount collected (₹)
                </label>
                <input
                  id="onboarding-amount"
                  type="number"
                  min="0"
                  step="0.01"
                  value={state.amount}
                  onChange={(e) => onChange({ amount: e.target.value })}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                {errors.amount && <p className="text-sm text-red-600">{errors.amount}</p>}
              </div>
              <div className="space-y-1.5">
                <label htmlFor="onboarding-paynotes" className="block text-sm font-medium text-gray-700">
                  Note (optional)
                </label>
                <input
                  id="onboarding-paynotes"
                  type="text"
                  placeholder="e.g. inaugural discount"
                  value={state.paymentNotes}
                  onChange={(e) => onChange({ paymentNotes: e.target.value })}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" onClick={handleNextClick}>
          Next: Biometric
        </Button>
      </div>
    </div>
  );

  function handleNextClick() {
    if (validate()) onNext();
  }
}
