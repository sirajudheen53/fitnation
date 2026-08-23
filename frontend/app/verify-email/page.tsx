"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { CheckCircle2, XCircle, Mail, Loader2 } from "lucide-react";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { verifyEmail, resendVerification, ApiError } from "@/lib/api";

type VerifyState = "loading" | "success" | "error" | "resend";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");
  const registrationId = searchParams.get("registration_id");
  const [state, setState] = useState<VerifyState>(() => {
    return token ? "loading" : "error";
  });
  const [message, setMessage] = useState(() => {
    return token ? "" : "No verification token found. Please check your email link.";
  });
  const [resendEmail, setResendEmail] = useState("");
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (!token) {
      return;
    }

    async function doVerify() {
      try {
        const result = await verifyEmail(token || "");
        setState("success");
        setMessage(result.message);
        // Auto-redirect to plan selection after 2 seconds
        setTimeout(() => {
          router.push(`/select-plan?registration_id=${result.registration_id}`);
        }, 2000);
      } catch (err) {
        setState("error");
        if (err instanceof ApiError) {
          setMessage((err.data?.error as string | undefined) || err.message);
        } else {
          setMessage("Verification failed. Please try again.");
        }
      }
    }

    doVerify();
  }, [token, router]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resendEmail) return;
    setResending(true);
    try {
      const result = await resendVerification(resendEmail);
      setState("resend");
      setMessage(result.message);
    } catch (err) {
      if (err instanceof ApiError) {
        setMessage((err.data?.error as string | undefined) || err.message);
      } else {
        setMessage("Failed to resend. Please try again.");
      }
    } finally {
      setResending(false);
    }
  };

  // Loading state
  if (state === "loading") {
    return (
      <div className="flex flex-col items-center py-8">
        <Loader2 className="mb-4 h-12 w-12 animate-spin text-brand-500" />
        <p className="text-sm text-gray-500">Verifying your email…</p>
      </div>
    );
  }

  // Success state
  if (state === "success") {
    return (
      <div className="flex flex-col items-center py-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <CheckCircle2 className="h-8 w-8 text-green-600" />
        </div>
        <h2 className="mb-2 text-xl font-semibold text-gray-900">Email verified!</h2>
        <p className="mb-6 text-sm text-gray-500">{message}</p>
        <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
        <p className="mt-2 text-sm text-gray-500">Redirecting to plan selection…</p>
      </div>
    );
  }

  // Error or resend state
  return (
    <div>
      {state === "error" && (
        <div className="flex flex-col items-center py-6 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
            <XCircle className="h-8 w-8 text-red-600" />
          </div>
          <h2 className="mb-2 text-xl font-semibold text-gray-900">Verification failed</h2>
          <Alert variant="error" className="mb-6 text-left">
            {message}
          </Alert>
        </div>
      )}

      {state === "resend" && (
        <Alert variant="success" className="mb-6">
          {message}
        </Alert>
      )}

      <div className="border-t border-gray-100 pt-6">
        <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-gray-700">
          <Mail className="h-4 w-4" />
          Resend verification email
        </h3>
        <p className="mb-4 text-sm text-gray-500">
          Enter your email and we&apos;ll send a new verification link.
        </p>
        <form onSubmit={handleResend} className="space-y-3">
          <Input
            label="Email"
            type="email"
            placeholder="arjun@ironpeak.com"
            icon={<Mail className="h-4 w-4" />}
            value={resendEmail}
            onChange={(e) => setResendEmail(e.target.value)}
            required
          />
          <Button type="submit" fullWidth loading={resending}>
            Resend verification
          </Button>
        </form>
      </div>

      <p className="mt-6 text-center text-sm text-gray-500">
        <a href="/signup" className="font-medium text-brand-600 hover:text-brand-700">
          Back to sign up
        </a>
      </p>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <AuthLayout title="Verify Email">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
          </div>
        </AuthLayout>
      }
    >
      <AuthLayout
        title="Verify your email"
        subtitle="We sent a verification link to your inbox"
      >
        <VerifyEmailContent />
      </AuthLayout>
    </Suspense>
  );
}