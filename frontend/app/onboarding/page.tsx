"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ArrowRight, ArrowLeft, Check, Building2, MapPin, Phone, Dumbbell } from "lucide-react";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { completeOnboarding, type ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

const BUSINESS_TYPES = [
  { value: "gym", label: "Gym / Fitness Center" },
  { value: "yoga_studio", label: "Yoga Studio" },
  { value: "crossfit", label: "CrossFit Box" },
  { value: "personal_training", label: "Personal Training" },
  { value: "wellness_center", label: "Wellness Center" },
] as const;

const onboardingSchema = z.object({
  business_type: z.enum(["gym", "yoga_studio", "crossfit", "personal_training", "wellness_center"]),
  branches_count: z
    .number({ invalid_type_error: "Required" })
    .min(1, "At least 1 branch")
    .max(50, "Maximum 50 branches"),
  primary_branch_name: z
    .string()
    .min(2, "Branch name must be at least 2 characters")
    .max(200, "Branch name must not exceed 200 characters"),
  primary_branch_address: z
    .string()
    .min(5, "Please enter a complete address")
    .max(500, "Address must not exceed 500 characters"),
  primary_branch_phone: z
    .string()
    .min(7, "Please enter a valid phone number")
    .max(20, "Phone must not exceed 20 characters"),
});

type OnboardingFormData = z.infer<typeof onboardingSchema>;

const WIZARD_STEPS = ["business_type", "branch_info"] as const;
type WizardStep = (typeof WIZARD_STEPS)[number];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>("business_type");
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    trigger,
    watch,
    formState: { errors },
  } = useForm<OnboardingFormData>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      business_type: "gym",
      branches_count: 1,
    },
  });

  const selectedBusinessType = watch("business_type");

  const goToNext = async () => {
    const valid = await trigger(step === "business_type" ? "business_type" : ["primary_branch_name", "primary_branch_address", "primary_branch_phone"]);
    if (valid) {
      if (step === "business_type") {
        setStep("branch_info");
      }
    }
  };

  const goToPrev = () => {
    if (step === "branch_info") {
      setStep("business_type");
    }
  };

  const onSubmit = async (data: OnboardingFormData) => {
    setServerError(null);
    setSubmitting(true);
    const token = getToken();
    if (!token) {
      setServerError("Authentication token not found. Please select a plan first.");
      setSubmitting(false);
      return;
    }
    try {
      const result = await completeOnboarding(data, token);
      toast.success(result.message);
      router.push(result.redirect_to || "/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.data?.error || err.message);
      } else {
        setServerError("Failed to complete onboarding. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const currentStepIndex = WIZARD_STEPS.indexOf(step);

  return (
    <AuthLayout
      title="Set up your workspace"
      subtitle="Tell us about your business to get started"
    >
      {/* Step indicator */}
      <div className="mb-6 flex items-center justify-center gap-2">
        {WIZARD_STEPS.map((s, i) => (
          <div key={s} className="flex items-center">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                i < currentStepIndex
                  ? "bg-green-500 text-white"
                  : i === currentStepIndex
                    ? "bg-brand-600 text-white"
                    : "bg-gray-200 text-gray-500"
              }`}
            >
              {i < currentStepIndex ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            {i < WIZARD_STEPS.length - 1 && (
              <div
                className={`mx-1 h-0.5 w-12 ${i < currentStepIndex ? "bg-green-500" : "bg-gray-200"}`}
              />
            )}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError && (
          <Alert variant="error">{serverError}</Alert>
        )}

        {/* Step 1: Business Type */}
        {step === "business_type" && (
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">
                What type of business are you running?
              </label>
              <div className="grid grid-cols-1 gap-2">
                {BUSINESS_TYPES.map((bt) => (
                  <label
                    key={bt.value}
                    className={`flex cursor-pointer items-center gap-3 rounded-lg border-2 p-3 transition-all ${
                      selectedBusinessType === bt.value
                        ? "border-brand-500 bg-brand-50"
                        : "border-gray-200 hover:border-brand-300"
                    }`}
                  >
                    <input
                      type="radio"
                      value={bt.value}
                      {...register("business_type")}
                      className="sr-only"
                    />
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white">
                      <Dumbbell className="h-4 w-4 text-brand-600" />
                    </div>
                    <span className="text-sm font-medium text-gray-700">{bt.label}</span>
                    {selectedBusinessType === bt.value && (
                      <Check className="ml-auto h-4 w-4 text-brand-600" />
                    )}
                  </label>
                ))}
              </div>
              {errors.business_type?.message && (
                <p className="mt-1 text-sm text-red-600">{errors.business_type.message}</p>
              )}
            </div>

            <div>
              <Input
                label="How many branches do you have?"
                type="number"
                min={1}
                max={50}
                defaultValue={1}
                error={errors.branches_count?.message}
                hint="You can add more branches later"
                {...register("branches_count", { valueAsNumber: true })}
              />
            </div>

            <Button type="button" fullWidth size="lg" onClick={goToNext}>
              Continue
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Step 2: Branch Info */}
        {step === "branch_info" && (
          <div className="space-y-4">
            <div className="rounded-lg bg-brand-50 p-3 text-sm text-brand-800">
              <Building2 className="mb-1 inline h-4 w-4" /> Let&apos;s set up your primary branch
            </div>

            <Input
              label="Branch name"
              placeholder="Main Branch"
              icon={<Building2 className="h-4 w-4" />}
              error={errors.primary_branch_name?.message}
              {...register("primary_branch_name")}
            />

            <Input
              label="Branch address"
              placeholder="MG Road, Kochi, Kerala"
              icon={<MapPin className="h-4 w-4" />}
              error={errors.primary_branch_address?.message}
              {...register("primary_branch_address")}
            />

            <Input
              label="Branch phone"
              type="tel"
              placeholder="+91 484 123 4567"
              icon={<Phone className="h-4 w-4" />}
              error={errors.primary_branch_phone?.message}
              {...register("primary_branch_phone")}
            />

            <div className="flex gap-3">
              <Button type="button" variant="outline" onClick={goToPrev}>
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <Button type="submit" fullWidth size="lg" loading={submitting}>
                Complete setup
              </Button>
            </div>
          </div>
        )}
      </form>
    </AuthLayout>
  );
}