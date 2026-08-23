"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CreditCard, CalendarRange, Tag, DollarSign } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { MembershipPlan, MembershipPlanFormData, MembershipPlanType } from "@/types/membership";
import { errorMessage } from "@/lib/api";

const planSchema = z.object({
  name: z.string().min(1, "Plan name is required").max(100),
  price: z.coerce.number().min(0, "Price must be 0 or more"),
  duration_days: z.coerce.number().int().positive("Duration must be positive"),
  plan_type: z.enum(["monthly", "quarterly", "half_yearly", "yearly"]),
  description: z.string().max(500).optional().or(z.literal("")),
  is_active: z.boolean().default(true),
});

type PlanSchemaData = z.infer<typeof planSchema>;

const PLAN_TYPE_LABELS: Record<MembershipPlanType, string> = {
  monthly: "Monthly",
  quarterly: "Quarterly",
  half_yearly: "Half-yearly",
  yearly: "Yearly",
};

interface MembershipPlanFormProps {
  plan?: MembershipPlan;
  defaultValues?: Partial<MembershipPlanFormData>;
  submitLabel?: string;
  onSubmit: (data: MembershipPlanFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function MembershipPlanForm({
  plan,
  defaultValues,
  submitLabel = "Save plan",
  onSubmit,
  error,
  loading = false,
}: MembershipPlanFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<PlanSchemaData>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      name: "",
      price: 0,
      duration_days: 30,
      plan_type: "monthly",
      description: "",
      is_active: true,
      ...defaultValues,
    },
  });

  useEffect(() => {
    if (plan) {
      reset({
        name: plan.name,
        price: Number(plan.price) || 0,
        duration_days: plan.duration_days,
        plan_type: plan.plan_type,
        description: plan.description || "",
        is_active: plan.is_active,
      });
    }
  }, [plan, reset]);

  const handleFormSubmit = async (data: PlanSchemaData) => {
    const payload: MembershipPlanFormData = {
      name: data.name,
      price: data.price,
      duration_days: data.duration_days,
      plan_type: data.plan_type,
      description: data.description || undefined,
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
          label="Plan name"
          placeholder="Gold Membership"
          icon={<CreditCard className="h-4 w-4" />}
          error={errors.name?.message}
          {...register("name")}
        />
        <Input
          label="Price"
          type="number"
          step="0.01"
          min="0"
          placeholder="1999"
          icon={<DollarSign className="h-4 w-4" />}
          error={errors.price?.message}
          {...register("price")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Duration (days)"
          type="number"
          min="1"
          placeholder="30"
          icon={<Tag className="h-4 w-4" />}
          error={errors.duration_days?.message}
          {...register("duration_days")}
        />

        <div className="space-y-1.5">
          <label htmlFor="plan_type" className="block text-sm font-medium text-gray-700">
            Plan type
          </label>
          <select
            id="plan_type"
            {...register("plan_type")}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {(Object.keys(PLAN_TYPE_LABELS) as MembershipPlanType[]).map((type) => (
              <option key={type} value={type}>
                {PLAN_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
          {errors.plan_type?.message && (
            <p className="text-sm text-red-600">{errors.plan_type.message}</p>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="description" className="block text-sm font-medium text-gray-700">
          Description
        </label>
        <textarea
          id="description"
          rows={3}
          placeholder="What does this plan include?"
          {...register("description")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.description?.message && (
          <p className="text-sm text-red-600">{errors.description.message}</p>
        )}
      </div>

      <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
        <CalendarRange className="h-5 w-5 text-brand-600" />
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            {...register("is_active")}
            defaultChecked={isActive}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">Plan is active</span>
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
