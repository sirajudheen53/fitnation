"use client";

import { useState } from "react";
import { Copy, X } from "lucide-react";
import { toast } from "sonner";
import { Button, Card, CardBody } from "@/components/ui";
import { errorMessage, rotateAdminTenantCredentials } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { AdminRotateCredentialsResult, AdminTenant } from "@/types/admin";

interface RotateCredentialsDialogProps {
  tenant: AdminTenant;
  onClose: () => void;
}

export function RotateCredentialsDialog({ tenant, onClose }: RotateCredentialsDialogProps) {
  const [result, setResult] = useState<AdminRotateCredentialsResult | null>(null);
  const [rotating, setRotating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function rotate() {
    const token = getToken();
    if (!token) return;
    setRotating(true);
    setError(null);
    try {
      const res = await rotateAdminTenantCredentials(tenant.id, token);
      setResult(res);
      toast.success("Owner credentials rotated");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRotating(false);
    }
  }

  function copyPassword() {
    if (!result) return;
    navigator.clipboard.writeText(result.owner_password).then(
      () => toast.success("Password copied"),
      () => toast.error("Copy failed — select the password manually"),
    );
  }

  if (result) {
    /* ── One-time credential handover (mirrors the onboard success card) ── */
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <Card className="w-full max-w-md">
          <CardBody className="space-y-4 text-center">
            <div className="text-3xl">🔑</div>
            <h3 className="text-base font-semibold text-gray-900">
              Credentials rotated for {tenant.name}
            </h3>
            <p className="text-sm text-gray-500">
              Share these credentials with the gym owner — the password is shown
              only once.
            </p>
            <div className="space-y-2 rounded-lg bg-gray-50 p-4 text-left text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">Owner login</span>
                <span className="font-mono text-gray-900">{result.owner_email}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">New password</span>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-gray-900">{result.owner_password}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyPassword}
                    aria-label="Copy password"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-400">
              The previous password stopped working and all owner sessions were
              logged out.
            </p>
            <Button onClick={onClose} className="w-full">
              Done
            </Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  /* ── Confirmation ─────────────────────────────────────────────── */
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              Rotate Owner Credentials
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-sm text-gray-600">
            A new password will be generated for the owner of{" "}
            <span className="font-medium text-gray-900">{tenant.name}</span>.
          </p>
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            The current password stops working immediately and all owner
            sessions are logged out. This cannot be undone.
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={rotating}>
              Cancel
            </Button>
            <Button variant="danger" onClick={rotate} disabled={rotating}>
              {rotating ? "Rotating…" : "Rotate Credentials"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
