"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button, Card, CardBody, Input } from "@/components/ui";
import { errorMessage, updateAdminTenant } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { SUBSCRIPTION_PLANS, type AdminTenant } from "@/types/admin";

interface EditGymDialogProps {
  tenant: AdminTenant;
  onClose: () => void;
  /** Called with the updated tenant row so the list can swap it in. */
  onSaved: (updated: AdminTenant) => void;
}

export function EditGymDialog({ tenant, onClose, onSaved }: EditGymDialogProps) {
  const [name, setName] = useState(tenant.name);
  const [contactEmail, setContactEmail] = useState(tenant.contact_email);
  const [contactPhone, setContactPhone] = useState(tenant.contact_phone);
  const [plan, setPlan] = useState(tenant.subscription_plan);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  async function submit() {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      const updated = await updateAdminTenant(
        tenant.id,
        {
          name,
          contact_email: contactEmail,
          contact_phone: contactPhone,
          subscription_plan: plan,
        },
        token,
      );
      onSaved(updated);
    } catch (err) {
      const data = (err as { data?: unknown }).data;
      if (data && typeof data === "object" && !Array.isArray(data)) {
        const entries = Object.entries(data as Record<string, unknown>);
        if (entries.length) {
          setFieldErrors(
            Object.fromEntries(entries.map(([k, v]) => [k, Array.isArray(v) ? v : [String(v)]])),
          );
        }
      }
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Edit Gym</h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Input
            label="Gym name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={fieldErrors.name?.[0]}
          />
          <Input
            label="Contact email"
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            error={fieldErrors.contact_email?.[0]}
          />
          <Input
            label="Contact phone"
            value={contactPhone}
            onChange={(e) => setContactPhone(e.target.value)}
            error={fieldErrors.contact_phone?.[0]}
          />
          <div className="space-y-1.5">
            <label
              htmlFor="edit-gym-subscription-plan"
              className="block text-sm font-medium text-gray-700"
            >
              Subscription plan
            </label>
            <select
              id="edit-gym-subscription-plan"
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
            >
              {SUBSCRIPTION_PLANS.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.label}
                </option>
              ))}
            </select>
            {fieldErrors.subscription_plan?.[0] && (
              <p className="text-sm text-red-600">{fieldErrors.subscription_plan[0]}</p>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? "Saving…" : "Save Changes"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
