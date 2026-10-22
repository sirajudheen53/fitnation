"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button, Card, CardBody, Input } from "@/components/ui";
import { createAdminPlan, errorMessage, updateAdminPlan } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { SUBSCRIPTION_PLANS, type AdminSubscriptionPlan } from "@/types/admin";

interface PlanFormDialogProps {
  /** Present when editing an existing plan; null when creating. */
  plan: AdminSubscriptionPlan | null;
  onClose: () => void;
  onSaved: (saved: AdminSubscriptionPlan) => void;
}

/** Decimal-string prices as sent back by the DRF serializer. */
const DECIMAL_RE = /^\d+(\.\d{1,2})?$/;

export function PlanFormDialog({ plan, onClose, onSaved }: PlanFormDialogProps) {
  const editing = plan !== null;
  const [code, setCode] = useState(plan?.code ?? "starter");
  const [name, setName] = useState(plan?.name ?? "");
  const [priceMonthly, setPriceMonthly] = useState(plan?.price_monthly ?? "");
  const [priceYearly, setPriceYearly] = useState(plan?.price_yearly ?? "");
  const [maxBranches, setMaxBranches] = useState(String(plan?.max_branches ?? 1));
  const [maxCustomers, setMaxCustomers] = useState(String(plan?.max_customers ?? 100));
  const [maxTrainers, setMaxTrainers] = useState(String(plan?.max_trainers ?? 5));
  const [sortOrder, setSortOrder] = useState(String(plan?.sort_order ?? 0));
  const [isActive, setIsActive] = useState(plan?.is_active ?? true);
  const [featuresText, setFeaturesText] = useState(
    JSON.stringify(plan?.features ?? {}, null, 2),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  function validate(): Record<string, string[]> | null {
    const errors: Record<string, string[]> = {};
    if (!name.trim()) errors.name = ["Plan name is required."];
    if (!DECIMAL_RE.test(priceMonthly.trim()))
      errors.price_monthly = ["Enter a valid amount, e.g. 999 or 999.00."];
    if (!DECIMAL_RE.test(priceYearly.trim()))
      errors.price_yearly = ["Enter a valid amount, e.g. 9990 or 9990.00."];
    for (const [field, label, value] of [
      ["max_branches", "Max branches", maxBranches],
      ["max_customers", "Max customers", maxCustomers],
      ["max_trainers", "Max trainers", maxTrainers],
      ["sort_order", "Sort order", sortOrder],
    ] as const) {
      if (!/^\d+$/.test(value.trim()))
        errors[field] = [`${label} must be a whole number.`];
    }
    try {
      const parsed: unknown = JSON.parse(featuresText);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        errors.features = ["Features must be a JSON object, e.g. {\"whatsapp\": true}."];
      }
    } catch {
      errors.features = ["Features must be valid JSON."];
    }
    return Object.keys(errors).length ? errors : null;
  }

  async function submit() {
    const token = getToken();
    if (!token) return;
    const clientErrors = validate();
    if (clientErrors) {
      setFieldErrors(clientErrors);
      setError("Fix the highlighted fields before saving.");
      return;
    }
    setSaving(true);
    setError(null);
    setFieldErrors({});
    const payload = {
      code,
      name: name.trim(),
      price_monthly: priceMonthly.trim(),
      price_yearly: priceYearly.trim(),
      max_branches: Number(maxBranches),
      max_customers: Number(maxCustomers),
      max_trainers: Number(maxTrainers),
      sort_order: Number(sortOrder),
      is_active: isActive,
      features: JSON.parse(featuresText) as Record<string, unknown>,
    };
    try {
      const saved = editing
        ? await updateAdminPlan(plan.id, payload, token)
        : await createAdminPlan(payload, token);
      onSaved(saved);
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
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              {editing ? "Edit Subscription Plan" : "New Subscription Plan"}
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="space-y-1.5">
            <label
              htmlFor="plan-code"
              className="block text-sm font-medium text-gray-700"
            >
              Code
            </label>
            <select
              id="plan-code"
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:cursor-not-allowed disabled:bg-gray-50"
              value={code}
              disabled={editing}
              onChange={(e) => setCode(e.target.value)}
            >
              {SUBSCRIPTION_PLANS.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.label}
                </option>
              ))}
            </select>
            {editing && (
              <p className="text-xs text-gray-500">
                The code is the plan&apos;s permanent key — historical gyms reference it.
              </p>
            )}
            {fieldErrors.code?.[0] && (
              <p className="text-sm text-red-600">{fieldErrors.code[0]}</p>
            )}
          </div>
          <Input
            label="Plan name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={fieldErrors.name?.[0]}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Monthly price (₹)"
              type="number"
              min="0"
              step="0.01"
              value={priceMonthly}
              onChange={(e) => setPriceMonthly(e.target.value)}
              error={fieldErrors.price_monthly?.[0]}
            />
            <Input
              label="Yearly price (₹)"
              type="number"
              min="0"
              step="0.01"
              value={priceYearly}
              onChange={(e) => setPriceYearly(e.target.value)}
              error={fieldErrors.price_yearly?.[0]}
            />
            <Input
              label="Max branches"
              type="number"
              min="0"
              value={maxBranches}
              onChange={(e) => setMaxBranches(e.target.value)}
              error={fieldErrors.max_branches?.[0]}
            />
            <Input
              label="Max customers"
              type="number"
              min="0"
              value={maxCustomers}
              onChange={(e) => setMaxCustomers(e.target.value)}
              error={fieldErrors.max_customers?.[0]}
            />
            <Input
              label="Max trainers"
              type="number"
              min="0"
              value={maxTrainers}
              onChange={(e) => setMaxTrainers(e.target.value)}
              error={fieldErrors.max_trainers?.[0]}
            />
            <Input
              label="Sort order"
              type="number"
              min="0"
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              error={fieldErrors.sort_order?.[0]}
            />
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor="plan-features"
              className="block text-sm font-medium text-gray-700"
            >
              Features (JSON)
            </label>
            <textarea
              id="plan-features"
              rows={4}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 font-mono text-xs text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={featuresText}
              onChange={(e) => setFeaturesText(e.target.value)}
            />
            {fieldErrors.features?.[0] && (
              <p className="text-sm text-red-600">{fieldErrors.features[0]}</p>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Active — visible to new signups and admin onboarding
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? "Saving…" : editing ? "Save Changes" : "Create Plan"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
