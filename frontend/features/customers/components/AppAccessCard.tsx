"use client";

import { useState } from "react";
import { Smartphone } from "lucide-react";
import { toast } from "sonner";
import { Badge, Button, Card, CardBody, CardHeader } from "@/components/ui";
import { errorMessage, sendAppInvite } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Customer } from "@/types/customer";
import type { AppInviteBlock } from "@/types/onboarding";
import type { AppInviteStatusSummary } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";
import { todayISO } from "@/features/onboarding/lib/validity";
import { deriveAppAccessDisplay, describeInviteStatus } from "../lib/appAccess";

interface AppAccessCardProps {
  customer: Customer;
  /** This customer's memberships (null = not loaded → derivation limited). */
  memberships: Membership[] | null;
  /** All tenant plans (to resolve includes_app_access in the fallback). */
  plans: MembershipPlan[];
  /** Called after a successful invite send so the parent can refresh. */
  onInviteSent?: (invite: AppInviteBlock) => void;
}

/**
 * Customer detail → App access card (FBOS-011 F3): which plan grants app
 * access, validity/grace dates, and the invite action with delivery status.
 * The "why can't they log in?" debug surface for the front desk.
 */
export function AppAccessCard({
  customer,
  memberships,
  plans,
  onInviteSent,
}: AppAccessCardProps) {
  // Local override after a send; otherwise the (server-shaped) prop wins.
  const [override, setOverride] = useState<AppInviteStatusSummary | null>(null);
  const [sending, setSending] = useState(false);
  const invite = override ?? customer.app_invite_status ?? null;

  const display = deriveAppAccessDisplay(customer, memberships, plans, todayISO());
  const inviteDisplay = describeInviteStatus(invite);

  const handleSend = async () => {
    const token = getToken();
    if (!token) return;
    setSending(true);
    try {
      const fresh = await sendAppInvite(customer.id, token, inviteDisplay.force);
      toast.success(
        fresh.status === "sent"
          ? `Invite sent via ${fresh.channel === "sms" ? "SMS" : "WhatsApp"}`
          : fresh.status === "already_sent"
            ? "Invite was already sent recently"
            : `Invite ${fresh.status.replace("_", " ")}`,
      );
      setOverride({
        status: fresh.status,
        channel: fresh.channel,
        sent_at: fresh.sent_at,
        error_message: fresh.reason,
      });
      onInviteSent?.(fresh);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <Card data-testid="app-access-card">
      <CardHeader>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Smartphone className="h-5 w-5 text-brand-600" />
          App access
        </h2>
        <p className="text-sm text-gray-500">
          FitNation mobile app — the member&apos;s phone is their login (OTP).
        </p>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={display.variant} data-testid="app-access-state">
            {display.label}
          </Badge>
          {display.planName && (
            <span className="text-sm text-gray-700">
              via <span className="font-medium">{display.planName}</span>
            </span>
          )}
        </div>

        <div className="text-sm text-gray-600">
          {display.status === "active" && display.endDate && (
            <p>Membership valid until {display.endDate} — full app access.</p>
          )}
          {display.status === "grace" && (
            <p>
              Membership expired {display.endDate} — read-only until{" "}
              {display.graceEndDate ?? "—"}.
            </p>
          )}
          {display.status === "expired" && (
            <p>Membership expired {display.endDate} — app access is gated.</p>
          )}
          {display.status === "none" && (
            <p>This member&apos;s plan does not include the mobile app.</p>
          )}
          {display.status === "unknown" && (
            <p>No active membership — the app stays locked until they join a plan.</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-gray-100 pt-4">
          <Badge variant={inviteDisplay.variant} data-testid="app-invite-state">
            {inviteDisplay.label}
          </Badge>
          {inviteDisplay.actionLabel && (
            <Button size="sm" variant="outline" loading={sending} onClick={handleSend}>
              {inviteDisplay.actionLabel}
            </Button>
          )}
          {inviteDisplay.detail && (
            <span className="text-xs text-gray-500">{inviteDisplay.detail}</span>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
