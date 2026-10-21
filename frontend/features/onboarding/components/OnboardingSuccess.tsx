"use client";

import { useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  DoorOpen,
  ReceiptText,
  RefreshCw,
  Smartphone,
  UserRound,
} from "lucide-react";
import { Alert, Badge, Button, Card, CardBody } from "@/components/ui";
import type { DeviceSyncResult } from "@/types/access";
import type { AppInviteBlock, OnboardingResult } from "@/types/onboarding";
import { describeAppInvite, paymentMethodLabel } from "../lib/wizard";
import { formatDateLong } from "../lib/validity";

interface OnboardingSuccessProps {
  result: OnboardingResult;
  branchName: string | null;
  /** Send/resend the app invite; resolves the fresh invite block (null on failure). */
  onResendInvite: () => Promise<AppInviteBlock | null>;
  /** Re-push the allow-list to one device; resolves the sync result (null on failure). */
  onRetrySync: (deviceId: number) => Promise<DeviceSyncResult | null>;
  /** Reset the wizard to step 1, keeping the branch selection. */
  onOnboardNext: () => void;
}

export function OnboardingSuccess({
  result,
  branchName,
  onResendInvite,
  onRetrySync,
  onOnboardNext,
}: OnboardingSuccessProps) {
  const [invite, setInvite] = useState<AppInviteBlock>(result.app_invite);
  const [resending, setResending] = useState(false);
  const [syncRows, setSyncRows] = useState<Record<number, DeviceSyncResult | null>>({});
  const [retryingDevice, setRetryingDevice] = useState<number | null>(null);

  const chip = describeAppInvite(invite);
  const membership = result.membership;
  const entitlement = result.entitlement_preview;

  const handleResend = async () => {
    setResending(true);
    try {
      const fresh = await onResendInvite();
      if (fresh) setInvite(fresh);
    } finally {
      setResending(false);
    }
  };

  const handleRetrySync = async (deviceId: number) => {
    setRetryingDevice(deviceId);
    try {
      const sync = await onRetrySync(deviceId);
      setSyncRows((prev) => ({ ...prev, [deviceId]: sync }));
    } finally {
      setRetryingDevice(null);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5" data-testid="onboarding-success">
      <div className="text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-green-600">
          <CheckCircle2 className="h-7 w-7" />
        </div>
        <h2 className="mt-3 text-xl font-semibold text-gray-900">
          {result.returning_member ? "Welcome back!" : "Member onboarded 🎉"}
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          The member signs into the mobile app with their phone{" "}
          <span className="font-medium">+91{result.customer.phone}</span> using OTP —
          there is no password to hand over.
        </p>
      </div>

      {/* App invite — the point of the flow; kept front and center. */}
      <Card data-testid="app-invite-panel">
        <CardBody className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <Smartphone className="h-4 w-4 text-brand-600" />
            Mobile app invite
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant={chip.variant} data-testid="app-invite-chip">
              {chip.label}
            </Badge>
            {chip.resend && (
              <Button size="sm" variant="outline" loading={resending} onClick={handleResend}>
                <RefreshCw className="h-4 w-4" /> Resend invite
              </Button>
            )}
          </div>
          {chip.description && <p className="text-sm text-gray-500">{chip.description}</p>}
          {invite.sent_at && (
            <p className="text-xs text-gray-400">
              Last sent: {new Date(invite.sent_at).toLocaleString("en-IN")}
            </p>
          )}
          {entitlement && entitlement.status !== "none" && (
            <p className="text-sm text-gray-600">
              App access:{" "}
              <span className="font-medium">
                {entitlement.status === "grace"
                  ? `read-only until ${formatDateLong(entitlement.grace_end_date)}`
                  : `active until ${formatDateLong(entitlement.end_date)}`}
              </span>
            </p>
          )}
        </CardBody>
      </Card>

      {/* Member card */}
      <Card data-testid="member-card">
        <CardBody className="space-y-1">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <UserRound className="h-4 w-4 text-brand-600" />
            Member
          </div>
          <p className="mt-1 text-lg font-semibold text-gray-900">{result.customer.name}</p>
          <p className="text-sm text-gray-500">Phone: +91{result.customer.phone}</p>
          {membership && (
            <p className="text-sm text-gray-500">
              Plan: {membership.plan_name} · valid {formatDateLong(membership.start_date)} →{" "}
              {formatDateLong(membership.end_date)}
            </p>
          )}
          {branchName && <p className="text-sm text-gray-500">Branch: {branchName}</p>}
        </CardBody>
      </Card>

      {/* Door access */}
      {(result.biometrics.length > 0 || result.door_access.length > 0) && (
        <Card data-testid="door-access-panel">
          <CardBody className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <DoorOpen className="h-4 w-4 text-brand-600" />
              Door access
            </div>
            <div className="flex flex-wrap gap-2">
              {result.biometrics.map((row) => {
                const retried = syncRows[row.device_id];
                const synced = retried ? retried.synced : (row.sync?.synced ?? false);
                return (
                  <span
                    key={row.credential_id}
                    className="inline-flex items-center gap-2 rounded-full border border-gray-200 px-3 py-1 text-xs"
                  >
                    <Badge variant={synced ? "success" : "warning"}>
                      {row.device_name}: {synced ? "ACTIVE (synced)" : "saved — device offline"}
                    </Badge>
                    {!synced && (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 font-medium text-brand-600 hover:text-brand-700"
                        onClick={() => handleRetrySync(row.device_id)}
                        disabled={retryingDevice !== null}
                      >
                        <RefreshCw
                          className={`h-3 w-3 ${retryingDevice === row.device_id ? "animate-spin" : ""}`}
                        />
                        Retry sync
                      </button>
                    )}
                  </span>
                );
              })}
              {result.door_access
                .filter((row) => !result.biometrics.some((b) => b.device_id === row.device_id))
                .map((row) => (
                  <Badge key={row.device_id} variant={row.allowed ? "success" : "danger"}>
                    {row.reason}
                  </Badge>
                ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Payment receipt */}
      {(result.payment || result.invoice_number) && (
        <Card data-testid="payment-receipt">
          <CardBody className="space-y-1">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <ReceiptText className="h-4 w-4 text-brand-600" />
              Payment
            </div>
            {result.payment && (
              <p className="text-sm text-gray-600">
                {paymentMethodLabel(result.payment.method)} — ₹
                {Number(result.payment.amount).toLocaleString("en-IN")} ({result.payment.status})
              </p>
            )}
            {result.invoice_number && (
              <p className="text-sm text-gray-500">Invoice: {result.invoice_number}</p>
            )}
          </CardBody>
        </Card>
      )}

      {result.status === "pending_payment" && (
        <Alert variant="warning">
          Payment is still pending — the membership activates once the Razorpay checkout
          completes.
        </Alert>
      )}

      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
        <Link href={`/customers/${result.customer.id}`}>
          <Button variant="outline">View member profile</Button>
        </Link>
        <Button onClick={onOnboardNext}>Onboard next member</Button>
      </div>
    </div>
  );
}
