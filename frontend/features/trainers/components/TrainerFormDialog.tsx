"use client";

import { useEffect, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X, Plus } from "lucide-react";
import { Button, Card, CardBody, Input } from "@/components/ui";
import { createTrainer, errorMessage, updateTrainer } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Trainer } from "@/types/trainer";
import { certificationLabel } from "./trainers-shared";

const trainerSchema = z
  .object({
    first_name: z.string().trim().min(1, "First name is required.").max(150),
    last_name: z.string().trim().min(1, "Last name is required.").max(150),
    email: z.string().trim().email("Enter a valid email address."),
    phone: z.string().trim().max(20).optional().or(z.literal("")),
    /** Create-only: blank ⇒ the backend sets an unusable password. */
    password: z.string().max(128).optional().or(z.literal("")),
    specialization: z.string().trim().max(100).optional().or(z.literal("")),
    bio: z.string().trim().max(2000).optional().or(z.literal("")),
    certifications: z.array(z.string().trim().max(200)),
    experience_years: z.string().optional(),
    max_clients: z.string(),
    profile_photo: z
      .string()
      .trim()
      .url("Enter a valid URL (https://…).")
      .optional()
      .or(z.literal("")),
    is_active: z.boolean(),
  })
  .superRefine((data, ctx) => {
    const years = data.experience_years === "" ? undefined : Number(data.experience_years);
    if (years !== undefined && (!Number.isInteger(years) || years < 0)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["experience_years"],
        message: "Experience must be a whole number of years.",
      });
    }
    const max = Number(data.max_clients);
    if (!Number.isInteger(max) || max < 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["max_clients"],
        message: "Max clients must be a whole number of at least 1.",
      });
    }
  });

type TrainerFormValues = z.infer<typeof trainerSchema>;

interface TrainerFormDialogProps {
  /** Present when editing an existing trainer; null when creating. */
  trainer: Trainer | null;
  onClose: () => void;
  onSaved: (saved: Trainer) => void;
}

/**
 * Create/edit trainer dialog (issue #53).
 *
 * Create provisions the staff user (role=trainer) plus profile in one POST;
 * edit PATCHes the profile fields only — name/email/phone live on the user
 * record and are not editable here.
 */
export function TrainerFormDialog({ trainer, onClose, onSaved }: TrainerFormDialogProps) {
  const editing = trainer !== null;
  const [apiError, setApiError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState(false);
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<TrainerFormValues>({
    resolver: zodResolver(trainerSchema),
    defaultValues: {
      first_name: trainer?.first_name ?? "",
      last_name: trainer?.last_name ?? "",
      email: trainer?.email ?? "",
      phone: trainer?.phone ?? "",
      password: "",
      specialization: trainer?.specialization ?? "",
      bio: trainer?.bio ?? "",
      certifications: (trainer?.certifications ?? []).map(certificationLabel),
      experience_years: trainer?.experience_years != null ? String(trainer.experience_years) : "",
      max_clients: String(trainer?.max_clients ?? 50),
      profile_photo: trainer?.profile_photo ?? "",
      is_active: trainer?.is_active ?? true,
    },
  });

  // RHF's FieldArray typing doesn't accept primitive (string[]) fields as-is.
  const { fields, append, remove } = useFieldArray({
    control: control as never,
    name: "certifications",
  });

  // Re-seed when a different trainer is loaded into the dialog.
  useEffect(() => {
    reset({
      first_name: trainer?.first_name ?? "",
      last_name: trainer?.last_name ?? "",
      email: trainer?.email ?? "",
      phone: trainer?.phone ?? "",
      password: "",
      specialization: trainer?.specialization ?? "",
      bio: trainer?.bio ?? "",
      certifications: (trainer?.certifications ?? []).map(certificationLabel),
      experience_years: trainer?.experience_years != null ? String(trainer.experience_years) : "",
      max_clients: String(trainer?.max_clients ?? 50),
      profile_photo: trainer?.profile_photo ?? "",
      is_active: trainer?.is_active ?? true,
    });
  }, [trainer, reset]);

  async function submit(values: TrainerFormValues) {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setApiError(null);
    setFieldErrors({});
    const certifications = values.certifications
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    try {
      const saved = editing
        ? await updateTrainer(
            trainer.id,
            {
              specialization: values.specialization || "",
              bio: values.bio || "",
              is_active: values.is_active,
              certifications,
              experience_years:
                values.experience_years === "" ? undefined : Number(values.experience_years),
              max_clients: Number(values.max_clients),
              profile_photo: values.profile_photo || "",
            },
            token,
          )
        : await createTrainer(
            {
              email: values.email,
              first_name: values.first_name,
              last_name: values.last_name,
              phone: values.phone || undefined,
              password: values.password || undefined,
              specialization: values.specialization || "",
              bio: values.bio || "",
              certifications,
              experience_years:
                values.experience_years === "" ? 0 : Number(values.experience_years),
              max_clients: Number(values.max_clients),
              profile_photo: values.profile_photo || "",
            },
            token,
          );
      onSaved(saved);
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
      <Card className="max-h-[90vh] w-full max-w-2xl overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              {editing ? "Edit trainer" : "New trainer"}
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
            {apiError && <p className="text-sm text-red-600">{apiError}</p>}
            {!editing && (
              <p className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700">
                Creating a trainer also creates their staff login (role: trainer). Leave the
                password blank and they can set one via the verification email.
              </p>
            )}

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

            {!editing && (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <Input
                  label="Email"
                  type="email"
                  error={errors.email?.message ?? fieldErrors.email?.[0]}
                  {...register("email")}
                />
                <Input
                  label="Password (optional)"
                  type="password"
                  hint="Blank = set up via verification email"
                  error={errors.password?.message ?? fieldErrors.password?.[0]}
                  {...register("password")}
                />
              </div>
            )}
            {!editing && (
              <Input
                label="Phone"
                type="tel"
                error={errors.phone?.message ?? fieldErrors.phone?.[0]}
                {...register("phone")}
              />
            )}

            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Input
                label="Specialization"
                placeholder="Strength & Conditioning"
                error={errors.specialization?.message}
                {...register("specialization")}
              />
              <Input
                label="Experience (years)"
                type="number"
                min="0"
                error={errors.experience_years?.message}
                {...register("experience_years")}
              />
              <Input
                label="Max clients"
                type="number"
                min="1"
                error={errors.max_clients?.message}
                {...register("max_clients")}
              />
            </div>

            <Input
              label="Profile photo URL"
              placeholder="https://…"
              error={errors.profile_photo?.message}
              {...register("profile_photo")}
            />

            <div className="space-y-1.5">
              <label
                htmlFor="trainer-bio"
                className="block text-sm font-medium text-gray-700"
              >
                Bio
              </label>
              <textarea
                id="trainer-bio"
                rows={3}
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                {...register("bio")}
              />
              {errors.bio?.message && (
                <p className="text-sm text-red-600">{errors.bio.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <span className="block text-sm font-medium text-gray-700">Certifications</span>
              {fields.map((field, index) => (
                <div key={field.id} className="flex items-center gap-2">
                  <Input
                    aria-label={`Certification ${index + 1}`}
                    placeholder="e.g. ACE Certified Personal Trainer"
                    error={errors.certifications?.[index]?.message}
                    {...register(`certifications.${index}`)}
                    className="flex-1"
                  />
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-red-600"
                    aria-label={`Remove certification ${index + 1}`}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => append("")}
                className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                <Plus className="h-4 w-4" /> Add certification
              </button>
            </div>

            {editing && (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                  {...register("is_active")}
                />
                Active — visible in the trainers list and assignable
              </label>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="outline" type="button" onClick={onClose} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {editing ? "Save changes" : "Create trainer"}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
