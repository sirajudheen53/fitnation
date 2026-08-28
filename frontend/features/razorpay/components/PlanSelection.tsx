"use client";

import { useEffect, useState } from "react";
import { Check, CreditCard, User } from "lucide-react";
import { Alert, Button, Card, CardBody, CardHeader, Input, Spinner } from "@/components/ui";
import { errorMessage, fetchMembershipPlans } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { MembershipPlan } from "@/types/membership";

interface PlanSelectionProps {
  onSelect: (plan: MembershipPlan, customerId: number) => void;
}

/**
 * FBOS-031 — first step of the Razorpay checkout flow.
 *
 * Lets staff pick an active membership plan and the customer to bill, then
 * hands the selection off to the checkout step. The plan's price is used to
 * prefill the Razorpay order amount.
 */
export function PlanSelection({ onSelect }: PlanSelectionProps) {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [customerId, setCustomerId] = useState<string>("");
  const [customerError, setCustomerError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time auth guard before data fetch
      setError("You must be logged in to start a payment.");
      setLoading(false);
      return;
    }
    fetchMembershipPlans(token)
      .then((res) => setPlans(res.results.filter((p) => p.is_active)))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  const handleContinue = () => {
    const cid = Number(customerId);
    if (!Number.isInteger(cid) || cid <= 0) {
      setCustomerError("Customer ID is required");
      return;
    }
    setCustomerError(null);
    const plan = plans.find((p) => p.id === selectedPlanId);
    if (!plan) return;
    onSelect(plan, cid);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Select a plan</h2>
        <p className="text-sm text-gray-500">
          Choose the membership plan to collect payment for, then continue to Razorpay.
        </p>
      </CardHeader>
      <CardBody className="space-y-6">
        {plans.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-white py-12 text-center">
            <CreditCard className="h-10 w-10 text-gray-300" />
            <p className="mt-3 text-sm font-medium text-gray-900">No active plans</p>
            <p className="mt-1 text-sm text-gray-500">
              Create an active membership plan before collecting payment.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {plans.map((plan) => {
              const selected = selectedPlanId === plan.id;
              return (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => setSelectedPlanId(plan.id)}
                  aria-pressed={selected}
                  className={
                    selected
                      ? "relative rounded-xl border-2 border-brand-500 bg-brand-50 p-4 text-left ring-2 ring-brand-500/20"
                      : "relative rounded-xl border border-gray-200 bg-white p-4 text-left hover:border-brand-300"
                  }
                >
                  {selected && (
                    <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-white">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                  <h3 className="font-semibold text-gray-900">{plan.name}</h3>
                  <p className="mt-1 text-sm text-gray-500">{plan.duration_days} days</p>
                  <p className="mt-2 text-lg font-semibold text-brand-600">
                    ₹{Number(plan.price).toLocaleString("en-IN")}
                  </p>
                </button>
              );
            })}
          </div>
        )}

        <div className="max-w-sm">
          <Input
            label="Customer ID"
            type="number"
            min="1"
            placeholder="1"
            icon={<User className="h-4 w-4" />}
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            error={customerError ?? undefined}
          />
        </div>

        <div className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
          <span className="text-sm font-medium text-gray-700">Selected plan</span>
          <span className="text-sm font-semibold text-gray-900">
            {selectedPlanId
              ? plans.find((p) => p.id === selectedPlanId)?.name ?? "—"
              : "None selected"}
          </span>
        </div>

        <Button
          type="button"
          size="lg"
          fullWidth
          disabled={selectedPlanId === null}
          onClick={handleContinue}
        >
          Continue to payment
        </Button>
      </CardBody>
    </Card>
  );
}
