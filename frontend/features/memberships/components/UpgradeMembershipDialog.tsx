"use client";

import { useEffect, useState, type ChangeEvent } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CreditCard, DollarSign, StickyNote, X } from "lucide-react";
import { Button, Card, CardBody, Input, Spinner } from "@/components/ui";
import { errorMessage, fetchUpgradePreview, hasFieldErrors, upgradeMembership } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type {
  Membership,
  UpgradeMembershipData,
  UpgradeMembershipResponse,
  UpgradePreview,
} from "@/types/membership";
import type { PaymentMethod } from "@/types/payment";
import { formatMembershipDate } from "./MembershipTable";

const upgradeSchema = z.object({
  plan_id: z.coerce.number().int().positive("Pick a plan to upgrade to"),
  amount: z.coerce.number().positive("Amount must be greater than 0"),
  payment_method: z.enum(["cash", "card", "upi", "bank_transfer", "other"]),
  notes: z.string().max(500).optional().or(z.literal("")),
});

type UpgradeSchemaData = z.infer<typeof upgradeSchema>;

const METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: "Cash",
  card: "Card",
  upi: "UPI",
  bank_transfer: "Bank transfer",
  other: "Other",
};

/** Same method ordering as the record-payment form, so the desk sees one list. */
const METHOD_KEYS = Object.keys(METHOD_LABELS) as PaymentMethod[];

interface UpgradeMembershipDialogProps {
  membership: Membership;
  onClose: () => void;
  /** Receives the updated membership and the recorded payment on success. */
  onSaved: (membership: Membership, payment: UpgradeMembershipResponse["payment"]) => void;
}

/**
 * Plan-upgrade dialog (#105, owner decision 2026-11-07): the prorated price
 * difference is SUGGESTED — pre-filled and freely editable — and the entered
 * amount is what gets recorded as the payment. The end date stays UNCHANGED
 * (the upgrade swaps the plan within the already-paid window), spelled out in
 * the dialog so staff see it. The API call lives here so DRF field errors
 * render next to their inputs (#96) with the banner reserved for bodies
 * carrying nothing inline-renderable.
 */
export function UpgradeMembershipDialog({
  membership,
  onClose,
  onSaved,
}: UpgradeMembershipDialogProps) {
  const [preview, setPreview] = useState<UpgradePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<UpgradeSchemaData>({
    resolver: zodResolver(upgradeSchema),
    defaultValues: {
      plan_id: undefined,
      amount: undefined,
      payment_method: "cash",
      notes: "",
    },
  });

  // Degrade silently: a failed preview leaves the dialog unusable but the
  // message says why; the desk can still renew from the row.
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchUpgradePreview(membership.id, token)
      .then((data) => {
        setPreview(data);
        const first = data.eligible_plans[0];
        if (first) {
          setSelectedPlanId(first.id);
          setValue("plan_id", first.id, { shouldValidate: true, shouldDirty: true });
          setValue("amount", Number(first.suggested_amount), {
            shouldValidate: true,
            shouldDirty: true,
          });
        }
      })
      .catch((err) => setPreviewError(errorMessage(err)));
    // The membership is fixed for the dialog's lifetime; a re-open remounts it (key=).
  }, [membership.id, setValue]);

  /** Plan switches re-fill the amount with THAT plan's suggestion (editable). */
  const handlePlanChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const planId = Number(event.target.value);
    setSelectedPlanId(planId);
    setValue("plan_id", planId, { shouldValidate: true, shouldDirty: true });
    const option = preview?.eligible_plans.find((p) => p.id === planId);
    if (option) {
      setValue("amount", Number(option.suggested_amount), {
        shouldValidate: true,
        shouldDirty: true,
      });
    }
  };

  async function submit(values: UpgradeSchemaData) {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setApiError(null);
    setFieldErrors({});
    try {
      const data: UpgradeMembershipData = {
        plan_id: values.plan_id,
        amount: values.amount,
        payment_method: values.payment_method,
        notes: values.notes || undefined,
      };
      const result = await upgradeMembership(membership.id, data, token);
      onSaved(result.membership, result.payment);
    } catch (err) {
      // Surface DRF field errors on their inputs; everything else as a banner.
      const data = (err as { data?: unknown }).data;
      if (data && typeof data === "object" && !Array.isArray(data)) {
        const entries = Object.entries(data as Record<string, unknown>).filter(
          ([key]) => key !== "detail",
        );
        if (entries.length) {
          setFieldErrors(
            Object.fromEntries(
              entries.map(([k, v]) => [k, Array.isArray(v) ? v.map(String) : [String(v)]]),
            ),
          );
        }
      }
      // Field errors render next to their inputs (#96) — the banner only
      // carries bodies with nothing inline-renderable.
      if (!hasFieldErrors((err as { data?: unknown }).data)) {
        setApiError(errorMessage(err));
      }
      setSaving(false);
    }
  }

  const selectedOption =
    preview?.eligible_plans.find((p) => p.id === selectedPlanId) ??
    preview?.eligible_plans[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-md overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Upgrade membership</h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          <p className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700">
            The end date stays <span className="font-semibold">{formatMembershipDate(membership.end_date)}</span> —
            the upgrade swaps the plan within the already-paid window. The suggested amount is
            only a default: whatever you enter is recorded as the payment.
          </p>

          {previewError && <p className="text-sm text-red-600">{previewError}</p>}
          {apiError && <p className="text-sm text-red-600">{apiError}</p>}

          {!preview && !previewError && (
            <div className="flex h-20 items-center justify-center">
              <Spinner />
            </div>
          )}

          {preview && (
            <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
              <input type="hidden" {...register("plan_id")} />

              <div className="space-y-1.5">
                <label htmlFor="upgrade-plan" className="block text-sm font-medium text-gray-700">
                  Upgrade to
                </label>
                {preview.eligible_plans.length === 0 ? (
                  <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500">
                    No higher-priced plans available — every other plan costs the same or less
                    than {membership.plan_name}.
                  </p>
                ) : (
                  <div className="relative">
                    <select
                      id="upgrade-plan"
                      defaultValue={preview.eligible_plans[0]?.id}
                      onChange={handlePlanChange}
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    >
                      {preview.eligible_plans.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name} · ₹{Number(option.price).toLocaleString()} ·{" "}
                          {option.duration_days} days
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {fieldErrors.plan_id?.[0] && (
                  <p className="text-sm text-red-600">{fieldErrors.plan_id[0]}</p>
                )}
                {errors.plan_id?.message && (
                  <p className="text-sm text-red-600">{errors.plan_id.message}</p>
                )}
              </div>

              {selectedOption && (
                <p className="text-xs text-gray-500">
                  Suggested ₹{Number(selectedOption.suggested_amount).toLocaleString()} — prorated
                  for {preview.remaining_days} remaining{" "}
                  {preview.remaining_days === 1 ? "day" : "days"}. Change it freely.
                </p>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input
                  label="Amount"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="1050"
                  icon={<DollarSign className="h-4 w-4" />}
                  error={errors.amount?.message ?? fieldErrors.amount?.[0]}
                  {...register("amount")}
                />
                <div className="space-y-1.5">
                  <label htmlFor="upgrade-method" className="block text-sm font-medium text-gray-700">
                    Payment method
                  </label>
                  <div className="relative">
                    <CreditCard className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <select
                      id="upgrade-method"
                      {...register("payment_method")}
                      className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    >
                      {METHOD_KEYS.map((m) => (
                        <option key={m} value={m}>
                          {METHOD_LABELS[m]}
                        </option>
                      ))}
                    </select>
                  </div>
                  {(errors.payment_method?.message || fieldErrors.payment_method?.[0]) && (
                    <p className="text-sm text-red-600">
                      {errors.payment_method?.message ?? fieldErrors.payment_method?.[0]}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="upgrade-notes" className="block text-sm font-medium text-gray-700">
                  Notes
                </label>
                <div className="relative">
                  <StickyNote className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <textarea
                    id="upgrade-notes"
                    rows={2}
                    placeholder="Optional note for this upgrade payment"
                    {...register("notes")}
                    className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} disabled={saving} type="button">
                  Cancel
                </Button>
                <Button type="submit" disabled={preview.eligible_plans.length === 0} loading={saving}>
                  {saving ? "Upgrading…" : "Upgrade & record payment"}
                </Button>
              </div>
            </form>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
