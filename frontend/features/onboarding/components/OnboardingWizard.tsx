"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Alert, Spinner } from "@/components/ui";
import { StepWho } from "./StepWho";
import { StepPlanPayment } from "./StepPlanPayment";
import { StepBiometric } from "./StepBiometric";
import { OnboardingSuccess } from "./OnboardingSuccess";
import { buildOnboardingPayload, initialFormState } from "../lib/wizard";
import { computeDefaultWindow, todayISO } from "../lib/validity";
import {
  errorMessage,
  fetchBranches,
  fetchDevices,
  fetchMembershipPlans,
  onboardMember,
  searchCustomers,
  sendAppInvite,
  syncDevice,
  verifyOnboardingPayment,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Branch } from "@/types/branch";
import type { MembershipPlan } from "@/types/membership";
import type { AccessDevice, DeviceSyncResult } from "@/types/access";
import type { AppInviteBlock, OnboardingResult } from "@/types/onboarding";
import type { OnboardingFormState } from "../lib/wizard";

type WizardStep = 1 | 2 | 3;

const STEP_LABELS = ["Who", "Plan & payment", "Biometric"] as const;

/** Fresh idempotency key per wizard run (double-submit guard, design §4.5). */
function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `onb-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

interface OnboardingWizardProps {
  /** Preselect a branch (e.g. ?branch=2 deep link). */
  initialBranchId?: number | null;
}

export function OnboardingWizard({ initialBranchId = null }: OnboardingWizardProps) {
  const router = useRouter();

  const [step, setStep] = useState<WizardStep>(1);
  const [state, setState] = useState<OnboardingFormState>(() =>
    initialFormState(initialBranchId),
  );

  const [branches, setBranches] = useState<Branch[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [devices, setDevices] = useState<AccessDevice[] | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  /** Saved between the razorpay POST and verify for the retry path. */
  const [pendingOrder, setPendingOrder] = useState<OnboardingResult | null>(null);

  const patchState = useCallback((patch: Partial<OnboardingFormState>) => {
    setState((prev) => ({ ...prev, ...patch }));
  }, []);

  // Initial lookups: branches (preselect when the staff user has exactly one)
  // and the active plans for step 2.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/onboarding/member");
      return;
    }
    const authToken: string = token;
    fetchBranches(authToken)
      .then((list) => {
        const active = list.filter((b) => b.is_active);
        setBranches(active);
        // Default to the staff member's branch when it is unambiguous —
        // the stored user has no branch field, so a single-branch gym wins.
        setState((prev) =>
          prev.branchId !== null
            ? prev
            : { ...prev, branchId: active.length === 1 ? active[0].id : null },
        );
      })
      .catch((err) => toast.error(errorMessage(err)));
    fetchMembershipPlans(authToken)
      .then((res) => setPlans(res.results.filter((p) => p.is_active)))
      .catch((err) => toast.error(errorMessage(err)))
      .finally(() => setPlansLoading(false));
  }, [router]);

  // Step 3 entry: load the branch's active biometric devices. `devices ===
  // null` means loading; the reset to null happens in the step-2 transition
  // handler so no setState runs in the effect body.
  useEffect(() => {
    if (step !== 3 || devices !== null) return;
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    fetchDevices(authToken, { branch: state.branchId ?? undefined })
      .then((list) => setDevices(list.filter((d) => d.is_active)))
      .catch(() => setDevices([]));
  }, [step, devices, state.branchId]);

  const handlePhoneBlur = useCallback(
    (phone: string) => {
      const token = getToken();
      if (!token) return;
      const authToken: string = token;
      setLookupLoading(true);
      searchCustomers(authToken, phone)
        .then((matches) => {
          const exact = matches.find((c) => c.phone === phone) ?? matches[0] ?? null;
          patchState({ returningMember: exact });
        })
        .catch(() => patchState({ returningMember: null }))
        .finally(() => setLookupLoading(false));
    },
    [patchState],
  );

  const selectedPlan = plans.find((p) => p.id === state.planId) ?? null;

  const enterStep2 = () => {
    const plan = plans.find((p) => p.id === state.planId) ?? null;
    if (plan && state.startDate === "") {
      const window = computeDefaultWindow(plan.duration_days, todayISO());
      patchState({ startDate: window.start_date, endDate: window.end_date });
    }
    setStep(2);
  };

  const runRazorpayCheckout = useCallback(
    async (order: OnboardingResult): Promise<OnboardingResult | null> => {
      const token = getToken();
      const checkout = order.razorpay_checkout;
      if (!token || !checkout?.key || !checkout.order_id) {
        setSubmitError("Online payment is not configured — take cash instead or retry later.");
        return null;
      }
      const { loadRazorpayScript, openRazorpayCheckout } = await import(
        "@/features/razorpay/lib/razorpayCheckout"
      );
      const Razorpay = await loadRazorpayScript();
      return new Promise<OnboardingResult | null>((resolve) => {
        const instance = openRazorpayCheckout(Razorpay, {
          key: checkout.key,
          amount: checkout.amount ?? 0,
          currency: checkout.currency || "INR",
          name: "FitNation",
          description: "Membership payment",
          order_id: checkout.order_id as string,
          prefill: { contact: order.customer.phone, name: order.customer.name },
          modal: {
            ondismiss: () => resolve(null),
          },
          handler: (response) => {
            const authToken: string = token;
            verifyOnboardingPayment(order.onboarding_id, response, authToken)
              .then((final) => resolve(final))
              .catch((err) => {
                setSubmitError(errorMessage(err));
                resolve(null);
              });
          },
        });
        void instance;
      });
    },
    [],
  );

  const submit = useCallback(
    async (enrollBiometrics: boolean) => {
      if (!selectedPlan) return;
      const token = getToken();
      if (!token) {
        router.replace("/login?next=/onboarding/member");
        return;
      }
      const authToken: string = token;
      setSubmitting(true);
      setSubmitError(null);
      try {
        const payload = buildOnboardingPayload(
          enrollBiometrics ? state : { ...state, deviceId: null, deviceUserId: "" },
          selectedPlan,
        );
        const order = pendingOrder ?? (await onboardMember(payload, authToken, newIdempotencyKey()));
        setPendingOrder(order);
        if (order.status === "pending_payment" && order.razorpay_checkout) {
          const final = await runRazorpayCheckout(order);
          if (!final) {
            setSubmitError(
              "Payment didn't complete — retry the checkout or take cash (a fresh submit will use a new order).",
            );
            return;
          }
          setResult(final);
        } else {
          setResult(order);
        }
      } catch (err) {
        setSubmitError(errorMessage(err));
      } finally {
        setSubmitting(false);
      }
    },
    [pendingOrder, router, runRazorpayCheckout, selectedPlan, state],
  );

  const handleResendInvite = useCallback(async (): Promise<AppInviteBlock | null> => {
    const token = getToken();
    if (!token || !result) return null;
    const authToken: string = token;
    try {
      const fresh = await sendAppInvite(result.customer.id, authToken, true);
      toast.success("Invite resent");
      return fresh;
    } catch (err) {
      toast.error(errorMessage(err));
      return null;
    }
  }, [result]);

  const handleRetrySync = useCallback(
    async (deviceId: number): Promise<DeviceSyncResult | null> => {
      const token = getToken();
      if (!token) return null;
      const authToken: string = token;
      try {
        const sync = await syncDevice(deviceId, authToken);
        toast.success(sync.synced ? "Device synced" : "Device still offline");
        return sync;
      } catch (err) {
        toast.error(errorMessage(err));
        return null;
      }
    },
    [],
  );

  const handleOnboardNext = useCallback(() => {
    setState(initialFormState(state.branchId));
    setResult(null);
    setPendingOrder(null);
    setSubmitError(null);
    setStep(1);
  }, [state.branchId]);

  if (result) {
    const branchName = branches.find((b) => b.id === result.customer.branch)?.name ?? null;
    return (
      <OnboardingSuccess
        result={result}
        branchName={branchName}
        onResendInvite={handleResendInvite}
        onRetrySync={handleRetrySync}
        onOnboardNext={handleOnboardNext}
      />
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Progress stepper */}
      <ol className="flex items-center gap-2" aria-label="Onboarding progress">
        {STEP_LABELS.map((label, index) => {
          const value = (index + 1) as WizardStep;
          const active = step === value;
          const done = step > value;
          return (
            <li key={label} className="flex flex-1 items-center gap-2">
              <span
                aria-current={active ? "step" : undefined}
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  active
                    ? "bg-brand-600 text-white"
                    : done
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-500"
                }`}
              >
                {index + 1}
              </span>
              <span
                className={`text-sm font-medium ${active ? "text-gray-900" : "text-gray-500"}`}
              >
                {label}
              </span>
              {index < STEP_LABELS.length - 1 && (
                <span className="h-px flex-1 bg-gray-200" aria-hidden="true" />
              )}
            </li>
          );
        })}
      </ol>

      {submitError && <Alert variant="error">{submitError}</Alert>}
      {submitting && (
        <div className="flex items-center gap-2 text-sm text-gray-500" role="status">
          <Spinner className="h-4 w-4" /> Saving member…
        </div>
      )}

      {step === 1 && (
        <StepWho
          state={state}
          branches={branches}
          onChange={patchState}
          onPhoneBlur={handlePhoneBlur}
          lookupLoading={lookupLoading}
          onNext={enterStep2}
        />
      )}

      {step === 2 && (
        <StepPlanPayment
          state={state}
          plans={plans}
          loading={plansLoading}
          onChange={patchState}
          onBack={() => setStep(1)}
          onNext={() => {
            setDevices(null);
            setStep(3);
          }}
        />
      )}

      {step === 3 && (
        <StepBiometric
          state={state}
          devices={devices ?? []}
          loading={devices === null}
          onChange={patchState}
          onBack={() => setStep(2)}
          onSubmitWithBiometrics={() => void submit(true)}
          onSkip={() => void submit(false)}
          submitting={submitting}
        />
      )}

      {step !== 3 && (
        <p className="text-xs text-gray-400">
          Door access and the mobile-app invite are set up in step 3 — skipping biometrics
          never skips the invite.
        </p>
      )}
    </div>
  );
}
