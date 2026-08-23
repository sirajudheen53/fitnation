"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Tag, Percent, Calendar } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Coupon, CouponFormData } from "@/types/membership";
import { errorMessage } from "@/lib/api";

const couponSchema = z.object({
  code: z
    .string()
    .min(3, "Code must be at least 3 characters")
    .max(50)
    .regex(/^[A-Za-z0-9_-]+$/, "Only letters, numbers, - and _ allowed")
    .transform((v) => v.toUpperCase()),
  description: z.string().max(500).optional().or(z.literal("")),
  discount_type: z.enum(["percentage", "fixed"]),
  discount_value: z.coerce.number().positive("Discount must be positive"),
  valid_from: z.string().min(1, "Valid from is required"),
  valid_until: z.string().optional().or(z.literal("")),
  is_active: z.boolean().default(true),
});

type CouponSchemaData = z.infer<typeof couponSchema>;

interface CouponFormProps {
  coupon?: Coupon;
  defaultValues?: Partial<CouponFormData>;
  submitLabel?: string;
  onSubmit: (data: CouponFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function CouponForm({
  coupon,
  defaultValues,
  submitLabel = "Save coupon",
  onSubmit,
  error,
  loading = false,
}: CouponFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<CouponSchemaData>({
    resolver: zodResolver(couponSchema),
    defaultValues: {
      code: "",
      description: "",
      discount_type: "percentage",
      discount_value: 0,
      valid_from: "",
      valid_until: "",
      is_active: true,
      ...defaultValues,
    },
  });

  useEffect(() => {
    if (coupon) {
      reset({
        code: coupon.code,
        description: coupon.description || "",
        discount_type: coupon.discount_type,
        discount_value: coupon.discount_value,
        valid_from: coupon.valid_from,
        valid_until: coupon.valid_until || "",
        is_active: coupon.is_active,
      });
    }
  }, [coupon, reset]);

  const handleFormSubmit = async (data: CouponSchemaData) => {
    const payload: CouponFormData = {
      code: data.code,
      description: data.description || undefined,
      discount_type: data.discount_type,
      discount_value: data.discount_value,
      valid_from: data.valid_from,
      valid_until: data.valid_until || undefined,
      is_active: data.is_active,
    };
    await onSubmit(payload);
  };

  const isActive = watch("is_active");
  const discountType = watch("discount_type");

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Coupon code"
          placeholder="FIT10"
          icon={<Tag className="h-4 w-4" />}
          error={errors.code?.message}
          {...register("code")}
        />

        <div className="space-y-1.5">
          <label htmlFor="discount_type" className="block text-sm font-medium text-gray-700">
            Discount type
          </label>
          <select
            id="discount_type"
            {...register("discount_type")}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="percentage">Percentage (%)</option>
            <option value="fixed">Fixed amount</option>
          </select>
          {errors.discount_type?.message && (
            <p className="text-sm text-red-600">{errors.discount_type.message}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label={discountType === "percentage" ? "Discount %" : "Discount amount"}
          type="number"
          step="0.01"
          min="0"
          icon={discountType === "percentage" ? <Percent className="h-4 w-4" /> : <Tag className="h-4 w-4" />}
          error={errors.discount_value?.message}
          {...register("discount_value")}
        />
        <Input
          label="Valid from"
          type="date"
          icon={<Calendar className="h-4 w-4" />}
          error={errors.valid_from?.message}
          {...register("valid_from")}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="description" className="block text-sm font-medium text-gray-700">
          Description
        </label>
        <textarea
          id="description"
          rows={2}
          placeholder="Optional note about this coupon"
          {...register("description")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.description?.message && (
          <p className="text-sm text-red-600">{errors.description.message}</p>
        )}
      </div>

      <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
        <Percent className="h-5 w-5 text-brand-600" />
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            {...register("is_active")}
            defaultChecked={isActive}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">Coupon is active</span>
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
