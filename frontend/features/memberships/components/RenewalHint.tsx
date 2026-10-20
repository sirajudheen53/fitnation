"use client";

/**
 * Confusion-resolver hint: renewals extend the existing membership, assigning
 * creates a new one. Shown on the memberships and assign-membership pages.
 */
export function RenewalHint({ className = "" }: { className?: string }) {
  return (
    <p className={`text-sm text-gray-500 ${className}`}>
      Renewing with the same plan? Use <span className="font-medium text-gray-600">Renew</span> - it
      extends the same membership. Changing to a different plan? Assign a new membership.
    </p>
  );
}
