"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { User, Users, Building2 } from "lucide-react";
import { Button, Alert } from "@/components/ui";
import type { AssignmentFormData } from "@/types/trainer";
import type { Trainer } from "@/types/trainer";
import type { Customer } from "@/types/customer";
import { errorMessage } from "@/lib/api";

const assignmentSchema = z.object({
  trainer_id: z.coerce.number().int().positive("Select a trainer"),
  customer_id: z.coerce.number().int().positive("Select a customer"),
  branch_id: z.coerce.number().int().positive().optional().or(z.nan().transform(() => undefined)),
});

type AssignmentSchemaData = z.infer<typeof assignmentSchema>;

interface AssignmentFormProps {
  trainers: Trainer[];
  customers: Customer[];
  submitLabel?: string;
  onSubmit: (data: AssignmentFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function AssignmentForm({
  trainers,
  customers,
  submitLabel = "Assign trainer",
  onSubmit,
  error,
  loading = false,
}: AssignmentFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AssignmentSchemaData>({
    resolver: zodResolver(assignmentSchema),
    defaultValues: {
      trainer_id: undefined,
      customer_id: undefined,
      branch_id: undefined,
    },
  });

  const handleFormSubmit = async (data: AssignmentSchemaData) => {
    const payload: AssignmentFormData = {
      trainer_id: data.trainer_id,
      customer_id: data.customer_id,
      branch_id:
        data.branch_id !== undefined && !Number.isNaN(data.branch_id)
          ? data.branch_id
          : undefined,
    };
    await onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <div className="space-y-1.5">
        <label htmlFor="trainer_id" className="block text-sm font-medium text-gray-700">
          Trainer
        </label>
        <div className="relative">
          <Users className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <select
            id="trainer_id"
            {...register("trainer_id")}
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select trainer</option>
            {trainers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name}
                {t.specialization ? ` — ${t.specialization}` : ""}
              </option>
            ))}
          </select>
        </div>
        {errors.trainer_id?.message && (
          <p className="text-sm text-red-600">{errors.trainer_id.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="customer_id" className="block text-sm font-medium text-gray-700">
          Customer
        </label>
        <div className="relative">
          <User className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <select
            id="customer_id"
            {...register("customer_id")}
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.first_name} {c.last_name} ({c.email})
              </option>
            ))}
          </select>
        </div>
        {errors.customer_id?.message && (
          <p className="text-sm text-red-600">{errors.customer_id.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="branch_id" className="block text-sm font-medium text-gray-700">
          Branch ID (optional)
        </label>
        <div className="relative">
          <Building2 className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            id="branch_id"
            type="number"
            min="1"
            placeholder="1"
            {...register("branch_id")}
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        {errors.branch_id?.message && (
          <p className="text-sm text-red-600">{errors.branch_id.message}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

