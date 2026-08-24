"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Mail, Lock, Eye, EyeOff } from "lucide-react";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { login, ApiError } from "@/lib/api";
import { setToken, setStoredUser, type StoredUser } from "@/lib/auth";

const loginSchema = z.object({
  email: z
    .string()
    .email("Please enter a valid email address")
    .min(1, "Email is required"),
  password: z
    .string()
    .min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/dashboard";
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null);
    try {
      const result = await login({
        email: data.email,
        password: data.password,
        device_type: "web",
      });

      // Persist token + user
      setToken(result.token);
      const storedUser: StoredUser = {
        id: result.user.id,
        email: result.user.email,
        name: result.user.name,
        role: result.user.role,
        tenant_id: result.user.tenant_id,
        tenant_name: result.user.tenant_name,
        is_owner: result.user.is_owner,
      };
      setStoredUser(storedUser);

      // Store permissions
      if (typeof window !== "undefined") {
        localStorage.setItem("fbos_permissions", JSON.stringify(result.permissions));
      }

      toast.success(`Welcome back, ${result.user.name || result.user.email}!`);
      router.push(next);
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError((err.data?.detail || err.data?.error || err.message) as string);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  };

  return (
    <AuthLayout
      title="Sign in to your account"
      subtitle="Welcome back to FitNation FBOS"
      footer={
        <>
          Don&apos;t have an account?{" "}
          <a href="/signup" className="font-medium text-brand-600 hover:text-brand-700">
            Create one
          </a>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError && (
          <Alert variant="error">{serverError}</Alert>
        )}

        <Input
          label="Email"
          type="email"
          placeholder="admin@gym.com"
          icon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register("email")}
          autoComplete="email"
          autoFocus
        />

        <div className="relative">
          <Input
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="Enter your password"
            icon={<Lock className="h-4 w-4" />}
            error={errors.password?.message}
            {...register("password")}
            autoComplete="current-password"
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
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}