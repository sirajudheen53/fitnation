"use client";

import { useState } from "react";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { formatMembershipDate } from "./MembershipTable";
import { renewalDays, renewalNewEndDate } from "@/features/memberships/lib/renewal";
import type { Membership, MembershipPlan } from "@/types/membership";

interface RenewMembershipDialogProps {
  membership: Membership;
  /** Tenant plans — the plan switcher options and the preview durations. */
  plans: MembershipPlan[];
  busy?: boolean;
  /**
   * Called with the renewal days (undefined lets the backend apply its
   * default) and the selected plan id — undefined when it's still the
   * membership's current plan (issue #68: plan_id travels only on a switch).
   */
  onConfirm: (days: number | undefined, planId: number | undefined) => void;
  onClose: () => void;
}

/**
 * Renewal confirmation: shows the customer, the selected plan (default =
 * current), current end date and the computed new end date so the owner can
 * see the SAME membership gets extended — optionally moved onto a different
 * plan before the extension (no new membership record is created).
 */
export function RenewMembershipDialog({
  membership,
  plans,
  busy = false,
  onConfirm,
  onClose,
}: RenewMembershipDialogProps) {
  const [selectedPlanId, setSelectedPlanId] = useState(membership.plan_id);
  const planChanged = selectedPlanId !== membership.plan_id;

  const days = renewalDays(membership, plans, selectedPlanId);
  const newEnd = renewalNewEndDate(membership, plans, selectedPlanId);
  const selectedPlanName =
    plans.find((p) => p.id === selectedPlanId)?.name ?? membership.plan_name;

  // Keep the current plan selectable even when the tenant list doesn't
  // include it (stale plan or plans fetch failed) — the dropdown must never
  // render with no selection.
  const planOptions: { id: number; label: string }[] = plans.map((p) => ({
    id: p.id,
    label: `${p.name} · ${p.duration_days} days`,
  }));
  if (!plans.some((p) => p.id === membership.plan_id)) {
    planOptions.unshift({ id: membership.plan_id, label: membership.plan_name });
  }

  return (
    <ConfirmDialog
      title="Renew membership"
      confirmLabel="Renew"
      busy={busy}
      onConfirm={() =>
        onConfirm(days, planChanged ? selectedPlanId : undefined)
      }
      onClose={onClose}
    >
      <div className="space-y-1.5">
        <label
          htmlFor="renew-plan"
          className="block text-sm font-medium text-gray-700"
        >
          Plan
        </label>
        <select
          id="renew-plan"
          value={selectedPlanId}
          onChange={(e) => setSelectedPlanId(Number(e.target.value))}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          {planOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
        {planChanged && (
          <p className="text-xs text-brand-600">
            Renewal moves this membership to {selectedPlanName} before extending
            it.
          </p>
        )}
      </div>
      <p>
        Extend{" "}
        <span className="font-medium text-gray-900">{membership.customer_name}</span>
        &rsquo;s{" "}
        <span className="font-medium text-gray-900">{selectedPlanName}</span>{" "}
        membership by {days} days?
      </p>
      <p>
        Current end date:{" "}
        <span className="font-medium text-gray-900">
          {formatMembershipDate(membership.end_date)}
        </span>
      </p>
      <p>
        New end date:{" "}
        <span className="font-medium text-gray-900">
          {newEnd ? formatMembershipDate(newEnd) : "—"}
        </span>
      </p>
      <p className="text-xs text-gray-400">
        This extends the same membership — no new membership record is created.
      </p>
    </ConfirmDialog>
  );
}
