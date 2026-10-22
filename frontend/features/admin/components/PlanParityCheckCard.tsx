"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui";
import { errorMessage, getPlans } from "@/lib/api";
import { SUBSCRIPTION_PLANS, type AdminSubscriptionPlan } from "@/types/admin";

interface PlanParityCheckCardProps {
  /** The full admin plan list (active + inactive). */
  plans: AdminSubscriptionPlan[];
}

interface ParityProblems {
  /** Codes the onboarding/signup flows expect but that aren't active in the DB. */
  missingInDb: string[];
  /** Active plans a new signup's public catalog doesn't return. */
  missingInPublic: string[];
}

function findProblems(
  plans: AdminSubscriptionPlan[],
  publicCodes: string[],
): ParityProblems {
  const activeCodes = new Set(
    plans.filter((p) => p.is_active).map((p) => p.code),
  );
  const publicSet = new Set(publicCodes);
  const requiredCodes = SUBSCRIPTION_PLANS.map((p) => p.code);
  return {
    missingInDb: requiredCodes.filter((code) => !activeCodes.has(code)),
    missingInPublic: [...activeCodes].filter((code) => !publicSet.has(code)),
  };
}

/**
 * Plan seeding parity check (issue #44): confirms the plan catalog seeded
 * in the database is exactly what new signups (public /subscriptions/plans/)
 * and admin onboarding act on. A mismatch means onboarding or self-serve
 * signup is about to reject a plan code.
 */
export function PlanParityCheckCard({ plans }: PlanParityCheckCardProps) {
  const [publicCodes, setPublicCodes] = useState<string[] | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  const runCheck = useCallback(() => {
    setChecking(true);
    setFetchError(null);
    getPlans()
      .then((res) => setPublicCodes(res.plans.map((p) => p.code)))
      .catch((err: unknown) => setFetchError(errorMessage(err)))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => runCheck(), [runCheck]);

  const activeCount = plans.filter((p) => p.is_active).length;
  let body;
  if (checking) {
    body = <p className="text-sm text-gray-500">Checking seeding parity…</p>;
  } else if (fetchError) {
    body = (
      <p className="text-sm text-amber-800">
        Couldn&apos;t load the public plans catalog that new signups see: {fetchError}
      </p>
    );
  } else {
    const problems = findProblems(plans, publicCodes ?? []);
    const clean =
      problems.missingInDb.length === 0 && problems.missingInPublic.length === 0;
    body = clean ? (
      <p className="text-sm text-green-800">
        Seeding parity OK — {activeCount} active plan{activeCount === 1 ? "" : "s"}
        {" "}match the public catalog that new signups and admin onboarding see.
      </p>
    ) : (
      <div className="space-y-1 text-sm text-amber-800">
        <p>Parity check found problems:</p>
        <ul className="list-inside list-disc">
          {problems.missingInDb.map((code) => (
            <li key={code}>
              No active “{code}” plan in the database — onboarding and self-serve
              signup will reject it.
            </li>
          ))}
          {problems.missingInPublic.map((code) => (
            <li key={code}>
              Active plan “{code}” is missing from the public catalog new signups see.
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div
      className="mb-4 flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 sm:flex-row sm:items-start sm:justify-between"
      data-testid="plan-parity-check"
    >
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" />
        <div>
          <h2 className="text-sm font-semibold text-gray-900">Plan seeding parity</h2>
          {body}
        </div>
      </div>
      <Button variant="outline" size="sm" onClick={runCheck} disabled={checking}>
        <RefreshCw className="mr-2 h-4 w-4" /> Recheck
      </Button>
    </div>
  );
}

/** Exported for tests — mirrors the card's comparison logic. */
export { findProblems };
