"use client";

import { Badge } from "@/components/ui";
import type { PtRemaining } from "@/types/trainer";

/** Human copy for the machine-readable PT-pack `reason` (issues #54/#55). */
export function ptPackCopy(pack: PtRemaining): string {
  switch (pack.reason) {
    case "no_active_pt_membership":
      return "No active PT membership — sell a PT plan to enable sessions.";
    case "pt_membership_expired":
      return `PT membership expired${pack.end_date ? ` on ${pack.end_date}` : ""}.`;
    case "session_pack_exhausted":
      return `PT pack exhausted — all ${pack.total ?? pack.redeemed} sessions redeemed.`;
    default:
      return "";
  }
}

interface PtPackBadgeProps {
  pack: PtRemaining;
}

/**
 * PT session-pack meter (issue #54): "3 / 12 left" with a warning state when
 * booking is blocked. Render nothing for an absent pack — the caller decides
 * whether that hides the badge or shows an empty state.
 */
export function PtPackBadge({ pack }: PtPackBadgeProps) {
  if (pack.membership_status === "none") {
    return <Badge variant="default">No PT pack</Badge>;
  }
  if (pack.membership_status === "expired") {
    return (
      <Badge variant="warning" data-testid="pt-pack-badge">
        PT pack expired
      </Badge>
    );
  }
  if (pack.unlimited) {
    return (
      <Badge variant="success" data-testid="pt-pack-badge">
        PT pack: unlimited{pack.plan_name ? ` · ${pack.plan_name}` : ""}
      </Badge>
    );
  }
  const variant = pack.can_book ? "success" : "warning";
  return (
    <Badge variant={variant} data-testid="pt-pack-badge">
      PT pack: {pack.remaining} / {pack.total} left
      {pack.plan_name ? ` · ${pack.plan_name}` : ""}
    </Badge>
  );
}
