/**
 * Bulk app-invite orchestration for the members list (FBOS-011 F5).
 *
 * The backend has no batch endpoint yet — sends fan out to
 * POST /memberships/app-invite/ per member; the 24 h dedupe window keeps a
 * fan-out safe (worst case spam-protected, never financially wrong).
 */

import type { AppAccessDisplay } from "./appAccess";
import type { AppInviteStatusSummary, Customer } from "@/types/customer";
import type { AppInviteBlock } from "@/types/onboarding";

export interface BulkInviteOutcome {
  sent: number;
  already_sent: number;
  failed: number;
}

/**
 * A selected member is invitable when entitled (active or grace — both grant
 * `app.access`) and their last invite wasn't a successful send.
 */
export function isInvitable(
  display: AppAccessDisplay | undefined,
  invite: AppInviteStatusSummary | null | undefined,
): boolean {
  if (!display) return false;
  if (display.status !== "active" && display.status !== "grace") return false;
  return invite?.status !== "sent";
}

/** IDs from `selectedIds` that would actually receive an invite now. */
export function invitableIds(
  selectedIds: number[],
  appAccessByCustomer: Record<number, AppAccessDisplay>,
  customers: Customer[],
): number[] {
  return selectedIds.filter((id) => {
    const invite = customers.find((c) => c.id === id)?.app_invite_status;
    return isInvitable(appAccessByCustomer[id], invite);
  });
}

/**
 * Fan out invites, tolerating individual failures. `send` is injectable for
 * tests; callers pass `(id, token) => sendAppInvite(id, token, false)`.
 */
export async function sendBulkInvites(
  ids: number[],
  send: (id: number) => Promise<AppInviteBlock>,
): Promise<BulkInviteOutcome> {
  const results = await Promise.allSettled(ids.map((id) => send(id)));
  const outcome: BulkInviteOutcome = { sent: 0, already_sent: 0, failed: 0 };
  for (const result of results) {
    if (result.status === "rejected") {
      outcome.failed += 1;
    } else if (result.value.status === "sent") {
      outcome.sent += 1;
    } else if (result.value.status === "already_sent") {
      outcome.already_sent += 1;
    } else {
      // skipped / failed / not_applicable come back 200 with a status.
      outcome.failed += 1;
    }
  }
  return outcome;
}
