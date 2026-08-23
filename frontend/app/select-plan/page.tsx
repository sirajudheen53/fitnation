"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Check, Loader2, Sparkles, Crown, Rocket } from "lucide-react";
import { toast } from "sonner";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import {
  getPlans,
  selectPlan,
  type SubscriptionPlan,
  ApiError,
} from "@/lib/api";

type LoadingState = "loading" | "ready" | "submitting" | "error";

const PLAN_ICONS: Record<string, React.ElementType> = {
  starter: Rocket,
  professional: Sparkles,
  enterprise: Crown,
};

const PLAN_ACCENTS: Record<string, string> = {
  starter: "border-gray-200",
  professional: "border-brand-500 ring-2 ring-brand-500/20",
  enterprise: "border-gray-200",
};

const FEATURE_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp integration",
  ai_coach: "AI Coach",
  custom_branding: "Custom branding",
};

function SelectPlanContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const registrationId = searchParams.get("registration_id");
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [state, setState] = useState<LoadingState>(() => {
    return registrationId ? "loading" : "error";
  });
  const [error, setError] = useState(() => {
    return registrationId ? "" : "Missing registration ID. Please complete signup first.";
  });

  useEffect(() => {
    if (!registrationId) {
      return;
    }

    async function loadPlans() {
      try {
        const result = await getPlans();
        setPlans(result.plans);
        setState("ready");
      } catch (err) {
        setState("error");
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Failed to load plans. Please refresh the page.");
        }
      }
    }

    loadPlans();
  }, [registrationId]);

  const handleSelectPlan = async (planCode: string) => {
    if (!registrationId) return;
    setSelectedPlan(planCode);
    setState("submitting");
    try {
      const result = await selectPlan({
        registration_id: parseInt(registrationId, 10),
        plan_code: planCode,
      });
      toast.success(result.message);
      // Store the auth token
      localStorage.setItem("fbos_auth_token", result.auth_token);
      router.push("/onboarding");
    } catch (err) {
      setState("ready");
      setSelectedPlan(null);
      if (err instanceof ApiError) {
        setError((err.data?.error as string | undefined) || err.message);
      } else {
        setError("Failed to select plan. Please try again.");
      }
    }
  };

  if (state === "loading") {
    return (
      <div className="flex flex-col items-center py-12">
        <Loader2 className="mb-4 h-10 w-10 animate-spin text-brand-500" />
        <p className="text-sm text-gray-500">Loading subscription plans…</p>
      </div>
    );
  }

  if (state === "error" && plans.length === 0) {
    return (
      <div>
        <Alert variant="error" className="mb-6">{error}</Alert>
        <Button fullWidth onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && state === "error" && (
        <Alert variant="error" className="mb-2">{error}</Alert>
      )}

      {plans.map((plan) => {
        const Icon = PLAN_ICONS[plan.code] || Sparkles;
        const isSelected = selectedPlan === plan.code;
        const isSubmitting = state === "submitting" && isSelected;
        const isRecommended = plan.code === "professional";

        return (
          <div
            key={plan.code}
            className={`relative rounded-xl border-2 bg-white p-5 transition-all ${
              isSelected
                ? PLAN_ACCENTS[plan.code]
                : "border-gray-200 hover:border-brand-300"
            } ${isSubmitting ? "opacity-75" : ""}`}
          >
            {isRecommended && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="rounded-full bg-brand-600 px-3 py-1 text-xs font-semibold text-white">
                  Most Popular
                </span>
              </div>
            )}

            <div className="mb-4 flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50">
                  <Icon className="h-5 w-5 text-brand-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                  <p className="text-sm text-gray-500">
                    Up to {plan.max_branches} {plan.max_branches === 1 ? "branch" : "branches"}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-gray-900">
                  ₹{plan.price_monthly}
                </div>
                <div className="text-xs text-gray-500">/month</div>
              </div>
            </div>

            {/* Limits */}
            <div className="mb-4 grid grid-cols-3 gap-2 text-center text-xs">
              <div className="rounded-lg bg-gray-50 py-2">
                <div className="font-semibold text-gray-900">{plan.max_customers}</div>
                <div className="text-gray-500">Customers</div>
              </div>
              <div className="rounded-lg bg-gray-50 py-2">
                <div className="font-semibold text-gray-900">{plan.max_trainers}</div>
                <div className="text-gray-500">Trainers</div>
              </div>
              <div className="rounded-lg bg-gray-50 py-2">
                <div className="font-semibold text-gray-900">{plan.max_branches}</div>
                <div className="text-gray-500">Branches</div>
              </div>
            </div>

            {/* Features */}
            <ul className="mb-5 space-y-2">
              {Object.entries(plan.features).map(([key, enabled]) => (
                <li key={key} className="flex items-center gap-2 text-sm">
                  {enabled ? (
                    <Check className="h-4 w-4 flex-shrink-0 text-green-500" />
                  ) : (
                    <span className="h-4 w-4 flex-shrink-0 text-gray-300">—</span>
                  )}
                  <span className={enabled ? "text-gray-700" : "text-gray-400"}>
                    {FEATURE_LABELS[key] || key}
                  </span>
                </li>
              ))}
            </ul>

            <Button
              fullWidth
              variant={isRecommended ? "primary" : "outline"}
              loading={isSubmitting}
              disabled={state === "submitting"}
              onClick={() => handleSelectPlan(plan.code)}
            >
              {isSubmitting ? "Provisioning workspace…" : `Select ${plan.name}`}
            </Button>
          </div>
        );
      })}

      {/* Yearly price note */}
      <p className="text-center text-xs text-gray-500">
        Yearly billing available — save ~2 months. Cancel anytime.
      </p>
    </div>
  );
}

export default function SelectPlanPage() {
  return (
    <Suspense
      fallback={
        <AuthLayout title="Select Plan">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
          </div>
        </AuthLayout>
      }
    >
      <AuthLayout
        title="Choose your plan"
        subtitle="Select a subscription tier for your fitness business"
      >
        <SelectPlanContent />
      </AuthLayout>
    </Suspense>
  );
}