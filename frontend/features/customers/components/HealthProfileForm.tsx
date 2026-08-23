"use client";

import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Ruler, Weight, Stethoscope, Activity, Target } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type {
  Customer,
  FitnessGoal,
  HealthProfileFormData,
} from "@/types/customer";
import { errorMessage } from "@/lib/api";

const healthProfileSchema = z.object({
  height_cm: z.coerce
    .number()
    .min(1, "Height must be greater than 0")
    .max(300, "Height seems too high")
    .optional()
    .or(z.nan().transform(() => undefined)),
  weight_kg: z.coerce
    .number()
    .min(1, "Weight must be greater than 0")
    .max(500, "Weight seems too high")
    .optional()
    .or(z.nan().transform(() => undefined)),
  bmi: z.coerce.number().nonnegative().optional().or(z.nan().transform(() => undefined)),
  fitness_goal: z
    .enum([
      "weight_loss",
      "muscle_gain",
      "endurance",
      "strength",
      "flexibility",
      "general_fitness",
      "rehabilitation",
      "sports_performance",
    ])
    .optional(),
  injuries: z.string().max(1000).optional().or(z.literal("")),
  medical_info: z.string().max(2000).optional().or(z.literal("")),
});

type HealthProfileSchemaData = z.infer<typeof healthProfileSchema>;

interface HealthProfileFormProps {
  customer?: Customer;
  onSubmit: (data: HealthProfileFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function calculateBmi(heightCm?: number, weightKg?: number): number | undefined {
  if (!heightCm || !weightKg || heightCm <= 0 || weightKg <= 0) return undefined;
  const heightM = heightCm / 100;
  const bmi = weightKg / (heightM * heightM);
  return Math.round(bmi * 10) / 10;
}

export function HealthProfileForm({
  customer,
  onSubmit,
  error,
  loading = false,
}: HealthProfileFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors },
  } = useForm<HealthProfileSchemaData>({
    resolver: zodResolver(healthProfileSchema),
    defaultValues: {
      height_cm: undefined,
      weight_kg: undefined,
      bmi: undefined,
      fitness_goal: undefined,
      injuries: "",
      medical_info: "",
    },
  });

  useEffect(() => {
    if (customer) {
      reset({
        height_cm: customer.height_cm ? parseFloat(String(customer.height_cm)) : undefined,
        weight_kg: customer.weight_kg ? parseFloat(String(customer.weight_kg)) : undefined,
        bmi: customer.bmi ? parseFloat(String(customer.bmi)) : undefined,
        fitness_goal: customer.fitness_goal ?? undefined,
        injuries: customer.injuries || "",
        medical_info: customer.medical_info || "",
      });
    }
  }, [customer, reset]);

  const heightCm = useWatch({ control, name: "height_cm" });
  const weightKg = useWatch({ control, name: "weight_kg" });

  const computedBmi = useMemo(
    () => calculateBmi(heightCm, weightKg),
    [heightCm, weightKg],
  );

  useEffect(() => {
    if (computedBmi !== undefined) {
      setValue("bmi", computedBmi, { shouldValidate: false });
    }
  }, [computedBmi, setValue]);

  const handleFormSubmit = async (data: HealthProfileSchemaData) => {
    const payload: HealthProfileFormData = {
      height_cm: data.height_cm,
      weight_kg: data.weight_kg,
      bmi: computedBmi ?? data.bmi,
      fitness_goal: data.fitness_goal as FitnessGoal | undefined,
      injuries: data.injuries || undefined,
      medical_info: data.medical_info || undefined,
    };
    await onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Input
          label="Height (cm)"
          type="number"
          step="0.1"
          placeholder="175"
          icon={<Ruler className="h-4 w-4" />}
          error={errors.height_cm?.message}
          {...register("height_cm")}
        />
        <Input
          label="Weight (kg)"
          type="number"
          step="0.1"
          placeholder="70"
          icon={<Weight className="h-4 w-4" />}
          error={errors.weight_kg?.message}
          {...register("weight_kg")}
        />
        <Input
          label="BMI (auto-calculated)"
          type="number"
          step="0.1"
          placeholder="22.9"
          icon={<Activity className="h-4 w-4" />}
          readOnly
          value={computedBmi ?? ""}
          {...register("bmi")}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="fitness_goal" className="block text-sm font-medium text-gray-700">
          <Target className="-mt-0.5 inline h-4 w-4" /> Fitness goal
        </label>
        <select
          id="fitness_goal"
          {...register("fitness_goal")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">Select goal</option>
          <option value="weight_loss">Weight loss</option>
          <option value="muscle_gain">Muscle gain</option>
          <option value="endurance">Endurance</option>
          <option value="strength">Strength</option>
          <option value="flexibility">Flexibility</option>
          <option value="general_fitness">General fitness</option>
          <option value="rehabilitation">Rehabilitation</option>
          <option value="sports_performance">Sports performance</option>
        </select>
        {errors.fitness_goal?.message && (
          <p className="text-sm text-red-600">{errors.fitness_goal.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="injuries" className="block text-sm font-medium text-gray-700">
          <Stethoscope className="-mt-0.5 inline h-4 w-4" /> Injuries / limitations
        </label>
        <textarea
          id="injuries"
          rows={3}
          placeholder="List any injuries, surgeries, or physical limitations"
          {...register("injuries")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.injuries?.message && (
          <p className="text-sm text-red-600">{errors.injuries.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="medical_info" className="block text-sm font-medium text-gray-700">
          Medical information
        </label>
        <textarea
          id="medical_info"
          rows={4}
          placeholder="Allergies, medications, conditions, doctor notes"
          {...register("medical_info")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.medical_info?.message && (
          <p className="text-sm text-red-600">{errors.medical_info.message}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>Save health profile</Button>
      </div>
    </form>
  );
}
