"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Building2,
  Mail,
  MapPin,
  Phone,
  Clock,
} from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Branch, BranchFormData } from "@/types/branch";
import { errorMessage } from "@/lib/api";

const branchSchema = z.object({
  name: z.string().min(1, "Branch name is required").max(200),
  branch_type: z.enum(["main", "sub"]),
  address_line1: z.string().min(1, "Street address is required").max(300),
  address_line2: z.string().max(300).optional().or(z.literal("")),
  city: z.string().min(1, "City is required").max(100),
  state: z.string().min(1, "State is required").max(100),
  postal_code: z
    .string()
    .min(1, "PIN code is required")
    .regex(/^\d{6}$/, "PIN code must be 6 digits"),
  country: z.string().min(1, "Country is required").max(100),
  phone: z
    .string()
    .optional()
    .or(z.literal(""))
    .refine((v) => !v || /^[+0-9\s-]{7,20}$/.test(v), {
      message: "Enter a valid phone number",
    }),
  email: z.string().email("Enter a valid email").optional().or(z.literal("")),
  opening_time: z.string().min(1, "Opening time is required"),
  closing_time: z.string().min(1, "Closing time is required"),
  operating_days: z.array(z.string()),
  is_active: z.boolean().default(true),
  is_headquarters: z.boolean().default(false),
});

type BranchSchemaData = z.infer<typeof branchSchema>;

export const OPERATING_DAY_OPTIONS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

interface BranchFormProps {
  branch?: Branch;
  defaultValues?: Partial<BranchFormData>;
  submitLabel?: string;
  onSubmit: (data: BranchFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function BranchForm({
  branch,
  defaultValues,
  submitLabel = "Save branch",
  onSubmit,
  error,
  loading = false,
}: BranchFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<BranchSchemaData>({
    resolver: zodResolver(branchSchema),
    defaultValues: {
      name: "",
      branch_type: "sub",
      address_line1: "",
      address_line2: "",
      city: "",
      state: "",
      postal_code: "",
      country: "India",
      phone: "",
      email: "",
      opening_time: "05:00",
      closing_time: "23:00",
      operating_days: [],
      is_active: true,
      is_headquarters: false,
      ...defaultValues,
    },
  });

  useEffect(() => {
    if (branch) {
      reset({
        name: branch.name,
        branch_type: branch.branch_type,
        address_line1: branch.address_line1,
        address_line2: branch.address_line2 || "",
        city: branch.city,
        state: branch.state,
        postal_code: branch.postal_code,
        country: branch.country,
        phone: branch.phone || "",
        email: branch.email || "",
        opening_time: branch.opening_time,
        closing_time: branch.closing_time,
        operating_days: branch.operating_days,
        is_active: branch.is_active,
        is_headquarters: branch.is_headquarters,
      });
    }
  }, [branch, reset]);

  const operatingDays = watch("operating_days") ?? [];
  const isActive = watch("is_active");
  const isHeadquarters = watch("is_headquarters");

  const toggleDay = (day: string) => {
    const current = operatingDays.includes(day)
      ? operatingDays.filter((d) => d !== day)
      : [...operatingDays, day];
    setValue("operating_days", current, { shouldValidate: true });
  };

  const handleFormSubmit = async (data: BranchSchemaData) => {
    const payload: BranchFormData = {
      name: data.name,
      branch_type: data.branch_type,
      address_line1: data.address_line1,
      address_line2: data.address_line2 || undefined,
      city: data.city,
      state: data.state,
      postal_code: data.postal_code,
      country: data.country,
      phone: data.phone || "",
      email: data.email || "",
      opening_time: data.opening_time,
      closing_time: data.closing_time,
      operating_days: data.operating_days,
      is_active: data.is_active,
      is_headquarters: data.is_headquarters,
    };
    await onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Branch name"
          placeholder="Downtown Gym"
          icon={<Building2 className="h-4 w-4" />}
          error={errors.name?.message}
          {...register("name")}
        />
        <div className="space-y-1.5">
          <label htmlFor="branch_type" className="block text-sm font-medium text-gray-700">
            Branch type
          </label>
          <select
            id="branch_type"
            {...register("branch_type")}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="main">Main branch</option>
            <option value="sub">Sub-branch</option>
          </select>
          {errors.branch_type?.message && (
            <p className="text-sm text-red-600">{errors.branch_type.message}</p>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-medium text-gray-700">Address</h3>
        <Input
          label="Street address"
          placeholder="123 Main Street"
          icon={<MapPin className="h-4 w-4" />}
          error={errors.address_line1?.message}
          {...register("address_line1")}
        />
        <Input
          label="Address line 2 (optional)"
          placeholder="Floor 2, Building B"
          error={errors.address_line2?.message}
          {...register("address_line2")}
        />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Input
            label="City"
            placeholder="Bengaluru"
            error={errors.city?.message}
            {...register("city")}
          />
          <Input
            label="State"
            placeholder="Karnataka"
            error={errors.state?.message}
            {...register("state")}
          />
          <Input
            label="PIN code"
            placeholder="560001"
            inputMode="numeric"
            maxLength={6}
            error={errors.postal_code?.message}
            {...register("postal_code")}
          />
        </div>
        <Input
          label="Country"
          placeholder="India"
          error={errors.country?.message}
          {...register("country")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Phone"
          type="tel"
          placeholder="+91 98765 43210"
          icon={<Phone className="h-4 w-4" />}
          error={errors.phone?.message}
          {...register("phone")}
        />
        <Input
          label="Email"
          type="email"
          placeholder="branch@example.com"
          icon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register("email")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Opening time"
          type="time"
          icon={<Clock className="h-4 w-4" />}
          error={errors.opening_time?.message}
          {...register("opening_time")}
        />
        <Input
          label="Closing time"
          type="time"
          icon={<Clock className="h-4 w-4" />}
          error={errors.closing_time?.message}
          {...register("closing_time")}
        />
      </div>

      <div className="space-y-2">
        <span className="block text-sm font-medium text-gray-700">Operating days</span>
        <div className="flex flex-wrap gap-2">
          {OPERATING_DAY_OPTIONS.map((day) => {
            const selected = operatingDays.includes(day);
            return (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                aria-pressed={selected}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  selected
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                {day}
              </button>
            );
          })}
        </div>
        {errors.operating_days?.message && (
          <p className="text-sm text-red-600">{errors.operating_days.message}</p>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setValue("is_active", e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">Branch is active</span>
        </label>
        <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
          <input
            type="checkbox"
            checked={isHeadquarters}
            onChange={(e) => setValue("is_headquarters", e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">Headquarters</span>
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
