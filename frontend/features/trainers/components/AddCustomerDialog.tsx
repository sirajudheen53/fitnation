"use client";

import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import { Button, Card, CardBody, Input, PhoneInput } from "@/components/ui";
import { addTrainerCustomer, errorMessage, fetchBranches } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { isAcceptablePhoneValue } from "@/lib/phone";
import type { Branch } from "@/types/branch";
import type { BranchTrainerAssignment } from "@/types/trainer";
import type { Customer } from "@/types/customer";
import type { Trainer } from "@/types/trainer";
import { trainerName } from "./trainers-shared";

const addCustomerSchema = z
  .object({
    first_name: z.string().trim().min(1, "First name is required.").max(150),
    last_name: z.string().trim().max(150).optional().or(z.literal("")),
    // Email is optional (msg 2438) — validate the format only when non-empty;
    // the "email or phone" rule is enforced in superRefine below.
    email: z
      .string()
      .trim()
      .email("Please enter a valid email")
      .optional()
      .or(z.literal("")),
    // PhoneInput emits E.164 (#88); empty is allowed — the "email or phone"
    // rule is enforced in superRefine below.
    phone: z
      .string()
      .max(20)
      .optional()
      .or(z.literal(""))
      .refine((v) => !v || isAcceptablePhoneValue(v), {
        message: "Enter a valid phone number.",
      }),
    branch_id: z
      .union([
        z.literal("").transform(() => undefined),
        z.nan().transform(() => undefined),
        z.coerce.number().int().positive(),
      ])
      .optional(),
  })
  .superRefine((data, ctx) => {
    // The backend rejects a member with neither channel ("Provide an email
    // or a phone number.") — surface it on the form first.
    if (!data.email?.trim() && !data.phone?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["email"],
        message: "Email or phone is required",
      });
    }
  });

type AddCustomerFormValues = z.infer<typeof addCustomerSchema>;

interface AddCustomerDialogProps {
  trainer: Trainer;
  onClose: () => void;
  onSaved: (customer: Customer, assignment: BranchTrainerAssignment) => void;
}

/**
 * "Add customer" dialog on the trainer profile (issue #73).
 *
 * The lightweight registration path: the essential member fields only —
 * name, one contact channel, branch — posted to
 * /trainers/{id}/add-customer/ which provisions the portal identity and
 * the branch-scoped assignment in one call. Everything else (address,
 * emergency contact, photo, admission fee) stays on the full customer
 * wizard at /customers/new.
 */
export function AddCustomerDialog({ trainer, onClose, onSaved }: AddCustomerDialogProps) {
  const [apiError, setApiError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState(false);
  const [branches, setBranches] = useState<Branch[]>([]);
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<AddCustomerFormValues>({
    resolver: zodResolver(addCustomerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      phone: "",
      branch_id: undefined,
    },
  });

  // Branch options for the assignment scope — degrade silently to a bare
  // "No branch" select when the list is unavailable (same as AssignTrainerModal).
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchBranches(token)
      .then(setBranches)
      .catch(() => setBranches([]));
  }, []);

  async function submit(values: AddCustomerFormValues) {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setApiError(null);
    setFieldErrors({});
    try {
      const { customer, assignment } = await addTrainerCustomer(
        trainer.id,
        {
          first_name: values.first_name,
          last_name: values.last_name || "",
          email: values.email?.trim() || "",
          phone: values.phone || "",
          branch_id: values.branch_id,
        },
        token,
      );
      onSaved(customer, assignment);
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
      setApiError(errorMessage(err));
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              Add customer to {trainerName(trainer)}
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          <p className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700">
            Registers a new member attached to this trainer. Address, emergency contact and
            plans can be added later from the customer&apos;s profile.
          </p>

          <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
            {apiError && <p className="text-sm text-red-600">{apiError}</p>}

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Input
                label="First name"
                error={errors.first_name?.message ?? fieldErrors.first_name?.[0]}
                {...register("first_name")}
              />
              <Input
                label="Last name"
                error={errors.last_name?.message ?? fieldErrors.last_name?.[0]}
                {...register("last_name")}
              />
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Input
                label="Email"
                type="email"
                error={errors.email?.message ?? fieldErrors.email?.[0]}
                {...register("email")}
              />
              <Controller
                control={control}
                name="phone"
                render={({ field }) => (
                  <PhoneInput
                    label="Phone"
                    error={errors.phone?.message ?? fieldErrors.phone?.[0]}
                    value={field.value ?? ""}
                    onChange={field.onChange}
                    autoComplete="tel"
                  />
                )}
              />
            </div>
            {!errors.email && !fieldErrors.email && (
              <p className="-mt-2 text-xs text-gray-500">
                One contact channel is required — email or phone.
              </p>
            )}

            <div className="space-y-1.5">
              <label
                htmlFor="add-customer-branch"
                className="block text-sm font-medium text-gray-700"
              >
                Branch
              </label>
              <select
                id="add-customer-branch"
                {...register("branch_id")}
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">No branch</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
              {fieldErrors.branch?.[0] && (
                <p className="text-sm text-red-600">{fieldErrors.branch[0]}</p>
              )}
              <p className="text-xs text-gray-500">
                The trainer linkage is branch-scoped — where this trainer coaches the member.
              </p>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" type="button" onClick={onClose} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving} aria-label="Confirm add customer">
                Add customer
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
