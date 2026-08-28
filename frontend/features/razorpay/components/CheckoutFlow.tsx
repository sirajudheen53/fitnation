"use client";

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import type { MembershipPlan } from "@/types/membership";
import { PlanSelection } from "./PlanSelection";
import { RazorpayCheckout, type CheckoutResult } from "./RazorpayCheckout";

interface CheckoutFlowProps {
  onComplete?: (result: CheckoutResult) => void;
}

/**
 * FBOS-031 — full Razorpay checkout flow.
 *
 * Step 1: select a membership plan + customer (PlanSelection).
 * Step 2: Razorpay checkout (order creation → modal → success/failure).
 */
export function CheckoutFlow({ onComplete }: CheckoutFlowProps) {
  const [step, setStep] = useState<"plan" | "checkout">("plan");
  const [selection, setSelection] = useState<{
    plan: MembershipPlan;
    customerId: number;
  } | null>(null);

  const handleSelect = (plan: MembershipPlan, customerId: number) => {
    setSelection({ plan, customerId });
    setStep("checkout");
  };

  if (step === "checkout" && selection) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={() => setStep("plan")}
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to plan selection
        </button>
        <RazorpayCheckout
          defaultAmount={Number(selection.plan.price)}
          defaultCustomer={selection.customerId}
          onComplete={onComplete}
        />
      </div>
    );
  }

  return <PlanSelection onSelect={handleSelect} />;
}
