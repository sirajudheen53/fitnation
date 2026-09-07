"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Mail,
  Phone,
  User,
  Calendar,
  Users,
  Building2,
  Activity,
} from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Customer, CustomerFormData, Gender } from "@/types/customer";
import { errorMessage, resolveMediaUrl } from "@/lib/api";
import { ProfilePhotoPicker, validateProfilePhoto } from "./ProfilePhotoPicker";

const customerSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  phone: z.string().max(20).optional().or(z.literal("")),
  // Untouched <select>/<input> elements submit as "" (or NaN for numbers),
  // so tolerate empty values instead of failing validation with cryptic
  // "Invalid enum value" messages.
  gender: z
    .enum(["male", "female", "other", "prefer_not_to_say"])
    .optional()
    .or(z.literal("")),
  date_of_birth: z.string().optional().or(z.literal("")),
  branch_id: z
    .union([
      z.literal("").transform(() => undefined),
      z.nan().transform(() => undefined),
      z.coerce.number().int().positive(),
    ])
    .optional(),
  emergency_contact_name: z.string().max(100).optional().or(z.literal("")),
  emergency_contact_phone: z.string().max(20).optional().or(z.literal("")),
  is_active: z.boolean().default(true),
});

type CustomerSchemaData = z.infer<typeof customerSchema>;

interface CustomerFormProps {
  customer?: Customer;
  defaultValues?: Partial<CustomerFormData>;
  submitLabel?: string;
  onSubmit: (data: CustomerFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function CustomerForm({
  customer,
  defaultValues,
  submitLabel = "Save customer",
  onSubmit,
  error,
  loading = false,
}: CustomerFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<CustomerSchemaData>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      email: "",
      first_name: "",
      last_name: "",
      phone: "",
      gender: undefined,
      date_of_birth: "",
      branch_id: undefined,
      emergency_contact_name: "",
      emergency_contact_phone: "",
      is_active: true,
      ...defaultValues,
    },
  });

  // Profile photo state (kept outside react-hook-form - it is a File, not text).
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoRemoved, setPhotoRemoved] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const existingPhotoUrl = resolveMediaUrl(customer?.profile_photo ?? null);

  useEffect(() => {
    if (customer) {
      // The backend stores a single `name`; best-effort split for the two inputs.
      const legacyFirst = customer.first_name || customer.name?.split(/\s+/)[0] || "";
      const legacyLast =
        customer.last_name || customer.name?.split(/\s+/).slice(1).join(" ") || "";
      reset({
        email: customer.email,
        first_name: legacyFirst,
        last_name: legacyLast,
        phone: customer.phone || "",
        gender: customer.gender ?? undefined,
        date_of_birth: customer.date_of_birth || "",
        branch_id: customer.branch ?? undefined,
        emergency_contact_name: customer.emergency_contact_name || "",
        emergency_contact_phone: customer.emergency_contact_phone || "",
        is_active: customer.is_active,
      });
      // Reloaded customer - drop any stale picker state.
      setPhotoFile(null);
      setPhotoRemoved(false);
      setPhotoError(null);
    }
  }, [customer, reset]);

  const handleFormSubmit = async (data: CustomerSchemaData) => {
    const payload: CustomerFormData = {
      email: data.email,
      first_name: data.first_name,
      last_name: data.last_name,
      phone: data.phone || undefined,
      gender: data.gender || undefined,
      date_of_birth: data.date_of_birth || undefined,
      branch_id:
        data.branch_id !== undefined && !Number.isNaN(data.branch_id)
          ? data.branch_id
          : undefined,
      emergency_contact_name: data.emergency_contact_name || undefined,
      emergency_contact_phone: data.emergency_contact_phone || undefined,
      is_active: data.is_active,
      profile_photo: photoFile ?? (photoRemoved ? null : undefined),
    };
    await onSubmit(payload);
  };

  const handlePhotoChange = (file: File | null) => {
    setPhotoError(null);
    if (!file) {
      setPhotoFile(null);
      return;
    }
    const validationError = validateProfilePhoto(file);
    if (validationError) {
      setPhotoError(validationError);
      return;
    }
    setPhotoFile(file);
    setPhotoRemoved(false);
  };

  const handlePhotoRemove = () => {
    setPhotoError(null);
    if (photoFile) {
      setPhotoFile(null);
      return;
    }
    setPhotoRemoved(true);
  };

  const isActive = watch("is_active");

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <ProfilePhotoPicker
        existingPhotoUrl={existingPhotoUrl}
        file={photoFile}
        removed={photoRemoved}
        error={photoError}
        onChange={handlePhotoChange}
        onRemove={handlePhotoRemove}
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="First name"
          placeholder="Arjun"
          icon={<User className="h-4 w-4" />}
          error={errors.first_name?.message}
          {...register("first_name")}
        />
        <Input
          label="Last name"
          placeholder="Kumar"
          icon={<User className="h-4 w-4" />}
          error={errors.last_name?.message}
          {...register("last_name")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Email"
          type="email"
          placeholder="arjun@example.com"
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="space-y-1.5">
          <label htmlFor="gender" className="block text-sm font-medium text-gray-700">
            Gender
          </label>
          <select
            id="gender"
            {...register("gender")}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
            <option value="prefer_not_to_say">Prefer not to say</option>
          </select>
          {errors.gender?.message && (
            <p className="text-sm text-red-600">{errors.gender.message}</p>
          )}
        </div>

        <Input
          label="Date of birth"
          type="date"
          icon={<Calendar className="h-4 w-4" />}
          error={errors.date_of_birth?.message}
          {...register("date_of_birth")}
        />

        <Input
          label="Branch ID"
          type="number"
          placeholder="1"
          icon={<Building2 className="h-4 w-4" />}
          error={errors.branch_id?.message}
          {...register("branch_id")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Emergency contact name"
          placeholder="Priya Kumar"
          icon={<Users className="h-4 w-4" />}
          error={errors.emergency_contact_name?.message}
          {...register("emergency_contact_name")}
        />
        <Input
          label="Emergency contact phone"
          type="tel"
          placeholder="+91 98765 43211"
          icon={<Phone className="h-4 w-4" />}
          error={errors.emergency_contact_phone?.message}
          {...register("emergency_contact_phone")}
        />
      </div>

      <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
        <Activity className="h-5 w-5 text-brand-600" />
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            {...register("is_active")}
            defaultChecked={isActive}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">Customer is active</span>
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
