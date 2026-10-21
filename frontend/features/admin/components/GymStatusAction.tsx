"use client";

import { useState } from "react";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { Button } from "@/components/ui";
import type { AdminTenant, AdminTenantSwitchStatus } from "@/types/admin";
import { ConfirmDialog } from "./ConfirmDialog";

interface GymStatusActionProps {
  tenant: AdminTenant;
  /**
   * Called with the target status once confirmed. The parent performs the
   * PATCH and updates its rows — resolving (or rejecting) settles the
   * button's loading state.
   */
  onChangeStatus: (tenant: AdminTenant, status: AdminTenantSwitchStatus) => Promise<void>;
  /** Rendered inert (archived gyms are read-only — PATCH cannot un-archive). */
  disabled?: boolean;
}

/**
 * Per-row Suspend/Activate control for the admin gyms table.
 * Suspension asks for confirmation first; activation is immediate.
 */
export function GymStatusAction(
  { tenant, onChangeStatus, disabled = false }: GymStatusActionProps,
) {
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);

  async function run(status: AdminTenantSwitchStatus) {
    setSaving(true);
    try {
      // The parent owns error reporting (toast) — absorb the rejection here
      // so it never surfaces as an unhandled promise rejection.
      await onChangeStatus(tenant, status).catch(() => undefined);
    } finally {
      setSaving(false);
      setConfirming(false);
    }
  }

  if (tenant.status === "suspended") {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        loading={saving}
        onClick={() => void run("active")}
      >
        <ShieldCheck className="mr-1 h-4 w-4 text-green-600" /> Activate
      </Button>
    );
  }

  return (
    <>
      <Button
        variant="danger"
        size="sm"
        disabled={disabled}
        loading={saving && !confirming}
        onClick={() => setConfirming(true)}
      >
        <ShieldOff className="mr-1 h-4 w-4" /> Suspend
      </Button>
      {confirming && (
        <ConfirmDialog
          title={`Suspend ${tenant.name}?`}
          confirmLabel="Suspend"
          destructive
          busy={saving}
          onConfirm={() => void run("suspended")}
          onClose={() => setConfirming(false)}
        >
          <p>Suspend this gym? Members lose access.</p>
        </ConfirmDialog>
      )}
    </>
  );
}