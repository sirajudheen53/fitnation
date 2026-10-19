"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button, Card, CardBody, Input } from "@/components/ui";
import { deleteAdminTenant, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { AdminTenant } from "@/types/admin";

interface ArchiveGymDialogProps {
  tenant: AdminTenant;
  onClose: () => void;
  /** Called with the archived tenant row so the list can swap it in. */
  onArchived: (updated: AdminTenant) => void;
}

export function ArchiveGymDialog({ tenant, onClose, onArchived }: ArchiveGymDialogProps) {
  const [confirmName, setConfirmName] = useState("");
  const [archiving, setArchiving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameMatches = confirmName.trim() === tenant.name;

  async function archive() {
    const token = getToken();
    if (!token || !nameMatches) return;
    setArchiving(true);
    setError(null);
    try {
      const updated = await deleteAdminTenant(tenant.id, token);
      onArchived(updated);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              Archive {tenant.name}?
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            <p>Archiving blocks owner logins and API access immediately.</p>
            <p>
              There is no un-archive action in this admin UI — recovery requires
              manual intervention.
            </p>
          </div>
          <Input
            label="Type the gym name to confirm"
            value={confirmName}
            onChange={(e) => setConfirmName(e.target.value)}
            placeholder={tenant.name}
            disabled={archiving}
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={archiving}>
              Cancel
            </Button>
            <Button variant="danger" onClick={archive} disabled={!nameMatches || archiving}>
              {archiving ? "Archiving…" : "Archive Gym"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
