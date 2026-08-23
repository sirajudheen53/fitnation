"use client";

import { useEffect } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Mail,
  Phone,
  User,
  Building2,
  Briefcase,
  Plus,
  X,
} from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Trainer, TrainerFormData } from "@/types/trainer";
import { errorMessage } from "@/lib/api";

const trainerSchema = z.object({
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  email: z.string().email("Please enter a valid email"),
  phone: z.string().max(20).optional().or(z.literal("")),
  specialization: z.string().max(100).optional().or(z.literal("")),
  bio: z.string().max(1000).optional().or(z.literal("")),
  certifications: z.array(z.string().max(100)),
  experience_years: z.coerce.number().int().min(0).optional().or(z.nan().transform(() => undefined)),
  branch_id: z.coerce.number().int().positive().optional().or(z.nan().transform(() => undefined)),
  is_active: z.boolean().default(true),
});

type TrainerSchemaData = z.infer<typeof trainerSchema>;

interface TrainerFormValues {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  specialization?: string;
  bio?: string;
  certifications: string[];
  experience_years?: number;
  branch_id?: number;
  is_active: boolean;
}

interface TrainerFormProps {
  trainer?: Trainer;
  defaultValues?: Partial<TrainerFormData>;
  submitLabel?: string;
  onSubmit: (data: TrainerFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function TrainerForm({
  trainer,
  defaultValues,
  submitLabel = "Save trainer",
  onSubmit,
  error,
  loading = false,
}: TrainerFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    formState: { errors },
  } = useForm<TrainerFormValues>({
    resolver: zodResolver(trainerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      phone: "",
      specialization: "",
      bio: "",
      certifications: [],
      experience_years: undefined,
      branch_id: undefined,
      is_active: true,
      ...defaultValues,
    },
  });

  const { fields, append, remove } = useFieldArray({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    control: control as any,
    name: "certifications",
  });

  useEffect(() => {
    if (trainer) {
      reset({
        first_name: trainer.first_name,
        last_name: trainer.last_name,
        email: trainer.email,
        phone: trainer.phone || "",
        specialization: trainer.specialization || "",
        bio: trainer.bio || "",
        certifications: trainer.certifications.length ? trainer.certifications : [""],
        experience_years: trainer.experience_years ?? undefined,
        branch_id: trainer.branch_id ?? undefined,
        is_active: trainer.is_active,
      });
    }
  }, [trainer, reset]);

  const handleFormSubmit = async (data: TrainerFormValues) => {
    const payload: TrainerFormData = {
      first_name: data.first_name,
      last_name: data.last_name,
      email: data.email,
      phone: data.phone || undefined,
      specialization: data.specialization || undefined,
      bio: data.bio || undefined,
      certifications: data.certifications.filter((c) => c.trim().length > 0),
      experience_years:
        data.experience_years !== undefined && !Number.isNaN(data.experience_years)
          ? data.experience_years
          : undefined,
      branch_id:
        data.branch_id !== undefined && !Number.isNaN(data.branch_id)
          ? data.branch_id
          : undefined,
      is_active: data.is_active,
    };
    await onSubmit(payload);
  };

  const isActive = watch("is_active");

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="First name"
          placeholder="Rahul"
          icon={<User className="h-4 w-4" />}
          error={errors.first_name?.message}
          {...register("first_name")}
        />
        <Input
          label="Last name"
          placeholder="Sharma"
          icon={<User className="h-4 w-4" />}
          error={errors.last_name?.message}
          {...register("last_name")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Email"
          type="email"
          placeholder="rahul@example.com"
          icon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register("email")}
        />
        <Input
          label="Phone"
          type="tel"
          placeholder="+91 98765 43210"
          icon={<Phone className="h-4 w-4" />}
          error={errors.phone?.message}
          {...register("phone")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Specialization"
          placeholder="Strength & Conditioning"
          icon={<Briefcase className="h-4 w-4" />}
          error={errors.specialization?.message}
          {...register("specialization")}
        />
        <Input
          label="Experience (years)"
          type="number"
          min="0"
          placeholder="5"
          error={errors.experience_years?.message}
          {...register("experience_years")}
        />
      </div>

      <Input
        label="Branch ID (optional)"
        type="number"
        min="1"
        placeholder="1"
        icon={<Building2 className="h-4 w-4" />}
        error={errors.branch_id?.message}
        {...register("branch_id")}
      />

      <div className="space-y-1.5">
        <label htmlFor="bio" className="block text-sm font-medium text-gray-700">
          Bio
        </label>
        <textarea
          id="bio"
          rows={3}
          placeholder="Short introduction about the trainer"
          {...register("bio")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.bio?.message && <p className="text-sm text-red-600">{errors.bio.message}</p>}
      </div>

      <div className="space-y-2">
        <span className="block text-sm font-medium text-gray-700">Certifications</span>
        {fields.map((field, index) => (
          <div key={field.id} className="flex items-center gap-2">
            <Input
              placeholder="e.g. ACE Certified Personal Trainer"
              {...register(`certifications.${index}`)}
              className="flex-1"
            />
            <button
              type="button"
              onClick={() => remove(index)}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-red-600"
              aria-label="Remove certification"
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

      <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
        <Briefcase className="h-5 w-5 text-brand-600" />
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            {...register("is_active")}
            defaultChecked={isActive}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">Trainer is active</span>
        </label>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

