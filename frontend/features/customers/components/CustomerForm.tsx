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
  MapPin,
  Home,
  Receipt,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Customer, CustomerFormData, Gender } from "@/types/customer";
import type { PaymentMethod } from "@/types/payment";
import { errorMessage, resolveMediaUrl } from "@/lib/api";
import { ProfilePhotoPicker, validateProfilePhoto } from "./ProfilePhotoPicker";

// Admission fees are collected as cash/UPI/card/other at the desk (msg 2438);
// online (Razorpay) and bank transfers go through the payments page.
const ADMISSION_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "upi", label: "UPI" },
  { value: "card", label: "Card" },
  { value: "other", label: "Other" },
];

const customerSchema = z
  .object({
    // Email is optional (msg 2438) — validate the format only when non-empty;
    // the "email or phone" rule is enforced in superRefine below.
    email: z
      .string()
      .trim()
      .email("Please enter a valid email")
      .optional()
      .or(z.literal("")),
    first_name: z.string().min(1, "First name is required").max(100),
    last_name: z.string().max(100).optional().or(z.literal("")),
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
    address_street: z.string().max(300).optional().or(z.literal("")),
    address_city: z.string().max(100).optional().or(z.literal("")),
    address_state: z.string().max(100).optional().or(z.literal("")),
    address_postal_code: z.string().max(20).optional().or(z.literal("")),
    // Admission-fee capture (create flow): the section keeps its amount as a
    // string and is only turned into a fee when a positive amount is entered.
    admission_amount: z.string().optional().or(z.literal("")),
    admission_timing: z.enum(["paid_now", "pending"]).default("paid_now"),
    admission_method: z
      .enum(["cash", "upi", "card", "other"])
      .default("cash"),
    is_active: z.boolean().default(true),
  })
  .superRefine((data, ctx) => {
    // A customer needs at least one contact channel (backend rejects with
    // "Provide an email or a phone number." — surface it on the form first).
    if (!data.email?.trim() && !data.phone?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["email"],
        message: "Email or phone is required",
      });
    }
    const amount = data.admission_amount?.trim();
    if (amount) {
      const parsed = Number(amount);
      if (!Number.isFinite(parsed) || parsed < 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["admission_amount"],
          message: "Enter a valid amount",
        });
      }
    }
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
    setValue,
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
      address_street: "",
      address_city: "",
      address_state: "",
      address_postal_code: "",
      admission_amount: "",
      admission_timing: "paid_now",
      admission_method: "cash",
      is_active: true,
      ...defaultValues,
    },
  });

  // Profile photo state (kept outside react-hook-form - it is a File, not text).
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoRemoved, setPhotoRemoved] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  // Admission-fee capture is a create-flow affordance; collapsed by default.
  const [feeOpen, setFeeOpen] = useState(false);
  const existingPhotoUrl = resolveMediaUrl(customer?.profile_photo ?? null);

  useEffect(() => {
    if (customer) {
      // The backend stores a single `name`; best-effort split for the two inputs.
      const legacyFirst = customer.first_name || customer.name?.split(/\s+/)[0] || "";
      const legacyLast =
        customer.last_name || customer.name?.split(/\s+/).slice(1).join(" ") || "";
      reset({
        email: customer.email ?? "",
        first_name: legacyFirst,
        last_name: legacyLast,
        phone: customer.phone || "",
        gender: customer.gender ?? undefined,
        date_of_birth: customer.date_of_birth || "",
        branch_id: customer.branch ?? undefined,
        emergency_contact_name: customer.emergency_contact_name || "",
        emergency_contact_phone: customer.emergency_contact_phone || "",
        address_street: customer.address_street || "",
        address_city: customer.address_city || "",
        address_state: customer.address_state || "",
        address_postal_code: customer.address_postal_code || "",
        admission_amount: "",
        admission_timing: "paid_now",
        admission_method: "cash",
        is_active: customer.is_active,
      });
      // Reloaded customer - drop any stale picker state.
      setPhotoFile(null);
      setPhotoRemoved(false);
      setPhotoError(null);
    }
  }, [customer, reset]);

  const handleFormSubmit = async (data: CustomerSchemaData) => {
    const feeAmount = Number(data.admission_amount?.trim() || 0);
    const payload: CustomerFormData = {
      email: data.email?.trim() || "",
      first_name: data.first_name,
      last_name: data.last_name || "",
      phone: data.phone || undefined,
      gender: data.gender || undefined,
      date_of_birth: data.date_of_birth || undefined,
      branch_id:
        data.branch_id !== undefined && !Number.isNaN(data.branch_id)
          ? data.branch_id
          : undefined,
      emergency_contact_name: data.emergency_contact_name || undefined,
      emergency_contact_phone: data.emergency_contact_phone || undefined,
      address_street: data.address_street || "",
      address_city: data.address_city || "",
      address_state: data.address_state || "",
      address_postal_code: data.address_postal_code || "",
      admission_fee:
        !customer && feeAmount > 0
          ? {
              amount: feeAmount,
              status: data.admission_timing === "pending" ? "pending" : "completed",
              method: data.admission_method,
            }
          : undefined,
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
  const feeTiming = watch("admission_timing");

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

      {/* Address (msg 2438): maps to the backend address_* fields. */}
      <div className="space-y-3">
        <p className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <MapPin className="h-4 w-4 text-brand-600" /> Address
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input
            label="Street"
            placeholder="12 MG Road"
            icon={<Home className="h-4 w-4" />}
            error={errors.address_street?.message}
            {...register("address_street")}
          />
          <Input
            label="City"
            placeholder="Bengaluru"
            error={errors.address_city?.message}
            {...register("address_city")}
          />
          <Input
            label="State"
            placeholder="Karnataka"
            error={errors.address_state?.message}
            {...register("address_state")}
          />
          <Input
            label="Postal code"
            placeholder="560001"
            error={errors.address_postal_code?.message}
            {...register("address_postal_code")}
          />
        </div>
      </div>

      {/* Admission fee capture (create flow only) — recorded as a payment
          row (kind=admission) by the caller after the customer is created. */}
      {!customer && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <button
            type="button"
            onClick={() => {
              if (feeOpen) {
                // Collapsing withdraws the fee — drop any entered amount.
                setValue("admission_amount", "");
              }
              setFeeOpen((open) => !open);
            }}
            aria-expanded={feeOpen}
            className="flex w-full items-center gap-3 p-4 text-left"
          >
            {feeOpen ? (
              <ChevronDown className="h-4 w-4 text-gray-500" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-500" />
            )}
            <Receipt className="h-5 w-5 text-brand-600" />
            <span className="text-sm font-medium text-gray-700">
              Admission fee <span className="font-normal text-gray-400">(optional)</span>
            </span>
          </button>
          {feeOpen && (
            <div className="grid grid-cols-1 gap-4 border-t border-gray-200 p-4 md:grid-cols-3">
              <Input
                label="Amount (₹)"
                type="number"
                min="0"
                step="0.01"
                placeholder="1000"
                error={errors.admission_amount?.message}
                {...register("admission_amount")}
              />
              <div className="space-y-1.5">
                <label
                  htmlFor="admission_timing"
                  className="block text-sm font-medium text-gray-700"
                >
                  Collection
                </label>
                <select
                  id="admission_timing"
                  {...register("admission_timing")}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="paid_now">Paid now</option>
                  <option value="pending">Pending</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="admission_method"
                  className="block text-sm font-medium text-gray-700"
                >
                  Method
                </label>
                <select
                  id="admission_method"
                  disabled={feeTiming === "pending"}
                  {...register("admission_method")}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500"
                >
                  {ADMISSION_METHODS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>
      )}

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
