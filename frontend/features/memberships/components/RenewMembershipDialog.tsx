"use client";

import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { formatMembershipDate } from "./MembershipTable";
import { renewalDays, renewalNewEndDate } from "@/features/memberships/lib/renewal";
import type { Membership, MembershipPlan } from "@/types/membership";

interface RenewMembershipDialogProps {
  membership: Membership;
  /** Tenant plans — used to resolve the renewal duration for the preview. */
  plans: MembershipPlan[];
  busy?: boolean;
  /** Called with the renewal days (undefined lets the backend apply its default). */
  onConfirm: (days: number | undefined) => void;
  onClose: () => void;
}

/**
 * Renewal confirmation: shows the customer, plan, current end date and the
 * computed new end date so the owner can see the SAME membership gets
 * extended (no new membership record is created).
 */
export function RenewMembershipDialog({
  membership,
  plans,
  busy = false,
  onConfirm,
  onClose,
}: RenewMembershipDialogProps) {
  const days = renewalDays(membership, plans);
  const newEnd = renewalNewEndDate(membership, plans);

  return (
    <ConfirmDialog
      title="Renew membership"
      confirmLabel="Renew"
      busy={busy}
      onConfirm={() => onConfirm(days)}
      onClose={onClose}
    >
      <p>
        Extend{" "}
        <span className="font-medium text-gray-900">{membership.customer_name}</span>
        &rsquo;s{" "}
        <span className="font-medium text-gray-900">{membership.plan_name}</span>{" "}
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
