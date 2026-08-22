"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Mail, Building2, User, Phone, Lock, Eye, EyeOff } from "lucide-react";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { signup, type ApiError } from "@/lib/api";

const signupSchema = z.object({
  business_name: z
    .string()
    .min(2, "Business name must be at least 2 characters")
    .max(200, "Business name must not exceed 200 characters"),
  contact_name: z
    .string()
    .min(2, "Contact name must be at least 2 characters")
    .max(200, "Contact name must not exceed 200 characters"),
  email: z
    .string()
    .email("Please enter a valid email address")
    .min(1, "Email is required"),
  phone: z
    .string()
    .max(20, "Phone must not exceed 20 characters")
    .optional()
    .or(z.literal("")),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Password must contain at least 1 uppercase letter")
    .regex(/[0-9]/, "Password must contain at least 1 digit"),
});

type SignupFormData = z.infer<typeof signupSchema>;

export default function SignUpPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
  });

  const onSubmit = async (data: SignupFormData) => {
    setServerError(null);
    try {
      const result = await signup({
        business_name: data.business_name,
        contact_name: data.contact_name,
        email: data.email,
        phone: data.phone || "",
        password: data.password,
      });
      toast.success(result.message);
      router.push(`/verify-email?registration_id=${result.registration_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const data = err.data;
        // Django DRF field errors
        const fieldErrors = Object.entries(data)
          .filter(([, v]) => Array.isArray(v))
          .map(([field, messages]) => {
            const msg = (messages as string[])[0];
            return `${field}: ${msg}`;
          });
        setServerError(fieldErrors[0] || err.message);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start managing your fitness business with FBOS"
      footer={
        <>
          Already have an account?{" "}
          <a href="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Sign in
          </a>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError && (
          <Alert variant="error">{serverError}</Alert>
        )}

        <Input
          label="Business name"
          placeholder="Iron Peak Gym"
          icon={<Building2 className="h-4 w-4" />}
          error={errors.business_name?.message}
          {...register("business_name")}
          autoComplete="organization"
        />

        <Input
          label="Contact name"
          placeholder="Arjun Kumar"
          icon={<User className="h-4 w-4" />}
          error={errors.contact_name?.message}
          {...register("contact_name")}
          autoComplete="name"
        />

        <Input
          label="Email"
          type="email"
          placeholder="arjun@ironpeak.com"
          icon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register("email")}
          autoComplete="email"
        />

        <Input
          label="Phone (optional)"
          type="tel"
          placeholder="+91 98765 43210"
          icon={<Phone className="h-4 w-4" />}
          error={errors.phone?.message}
          {...register("phone")}
          autoComplete="tel"
        />

        <div className="relative">
          <Input
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="Min 8 chars, 1 uppercase, 1 digit"
            icon={<Lock className="h-4 w-4" />}
            error={errors.password?.message}
            {...register("password")}
            autoComplete="new-password"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-9 text-gray-400 hover:text-gray-600"
            tabIndex={-1}
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>

        <Button type="submit" fullWidth size="lg" loading={isSubmitting}>
          Create account
        </Button>

        <p className="text-center text-xs text-gray-500">
          By creating an account, you agree to our Terms of Service and Privacy Policy.
        </p>
      </form>
    </AuthLayout>
  );
}