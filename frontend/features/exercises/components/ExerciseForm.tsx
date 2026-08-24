"use client";

import { useEffect } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, X, ListOrdered, Dumbbell, AlertTriangle, Link2 } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type {
  Exercise,
  ExerciseCategory,
  ExerciseDifficulty,
  ExerciseFormData,
} from "@/types/exercise";
import { errorMessage } from "@/lib/api";
import {
  DIFFICULTY_OPTIONS,
  MUSCLE_GROUP_OPTIONS,
  EQUIPMENT_OPTIONS,
} from "./helpers";

const exerciseSchema = z.object({
  name: z.string().min(1, "Name is required").max(200),
  description: z.string().max(5000).optional().or(z.literal("")),
  category: z.coerce.number().int().positive("Please select a category"),
  difficulty: z.enum(["beginner", "intermediate", "advanced"]),
  muscle_groups: z.array(z.string()),
  equipment_needed: z.array(z.string()),
  instructions: z.array(z.string()),
  media_url: z.string().url("Please enter a valid URL").optional().or(z.literal("")),
  tips: z.string().max(5000).optional().or(z.literal("")),
  contraindications: z.string().max(5000).optional().or(z.literal("")),
});

type ExerciseSchemaData = z.infer<typeof exerciseSchema>;

interface ExerciseFormProps {
  exercise?: Exercise;
  categories: ExerciseCategory[];
  defaultValues?: Partial<ExerciseFormData>;
  submitLabel?: string;
  onSubmit: (data: ExerciseFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function ExerciseForm({
  exercise,
  categories,
  defaultValues,
  submitLabel = "Save exercise",
  onSubmit,
  error,
  loading = false,
}: ExerciseFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    formState: { errors },
  } = useForm<ExerciseSchemaData>({
    resolver: zodResolver(exerciseSchema),
    defaultValues: {
      name: "",
      description: "",
      category: undefined,
      difficulty: "beginner",
      muscle_groups: [],
      equipment_needed: [],
      instructions: [""],
      media_url: "",
      tips: "",
      contraindications: "",
      ...defaultValues,
    },
  });

  const { fields: muscleFields, append: appendMuscle, remove: removeMuscle } =
    useFieldArray({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      control: control as any,
      name: "muscle_groups",
    });

  const { fields: equipmentFields, append: appendEquipment, remove: removeEquipment } =
    useFieldArray({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      control: control as any,
      name: "equipment_needed",
    });

  const { fields: instructionFields, append: appendInstruction, remove: removeInstruction } =
    useFieldArray({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      control: control as any,
      name: "instructions",
    });

  useEffect(() => {
    if (exercise) {
      reset({
        name: exercise.name,
        description: exercise.description,
        category: exercise.category,
        difficulty: exercise.difficulty,
        muscle_groups: exercise.muscle_groups.length
          ? exercise.muscle_groups
          : [""],
        equipment_needed: exercise.equipment_needed.length
          ? exercise.equipment_needed
          : [""],
        instructions: exercise.instructions.length
          ? exercise.instructions
          : [""],
        media_url: exercise.media_url || "",
        tips: exercise.tips,
        contraindications: exercise.contraindications,
      });
    }
  }, [exercise, reset]);

  const handleFormSubmit = async (data: ExerciseSchemaData) => {
    const payload: ExerciseFormData = {
      name: data.name,
      description: data.description || "",
      category: data.category,
      difficulty: data.difficulty as ExerciseDifficulty,
      muscle_groups: data.muscle_groups.filter((m) => m.trim().length > 0),
      equipment_needed: data.equipment_needed.filter((e) => e.trim().length > 0),
      instructions: data.instructions.filter((i) => i.trim().length > 0),
      media_url: data.media_url || undefined,
      tips: data.tips || undefined,
      contraindications: data.contraindications || undefined,
    };
    await onSubmit(payload);
  };

  const selectedMuscles = watch("muscle_groups");
  const selectedEquipment = watch("equipment_needed");

  const toggleMuscle = (group: string) => {
    const current = selectedMuscles.filter((m) => m.trim().length > 0);
    if (current.includes(group)) {
      const next = current.filter((m) => m !== group);
      reset({ ...watch(), muscle_groups: next.length ? next : [""] });
    } else {
      reset({ ...watch(), muscle_groups: [...current, group] });
    }
  };

  const toggleEquipment = (equipment: string) => {
    const current = selectedEquipment.filter((e) => e.trim().length > 0);
    if (current.includes(equipment)) {
      const next = current.filter((e) => e !== equipment);
      reset({ ...watch(), equipment_needed: next.length ? next : [""] });
    } else {
      reset({ ...watch(), equipment_needed: [...current, equipment] });
    }
  };

  const selectClass =
    "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      <Input
        label="Name"
        placeholder="Barbell Bench Press"
        icon={<Dumbbell className="h-4 w-4" />}
        error={errors.name?.message}
        {...register("name")}
      />

      <div className="space-y-1.5">
        <label htmlFor="description" className="block text-sm font-medium text-gray-700">
          Description
        </label>
        <textarea
          id="description"
          rows={3}
          placeholder="Short description of the exercise"
          {...register("description")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.description?.message && (
          <p className="text-sm text-red-600">{errors.description.message}</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <label htmlFor="category" className="block text-sm font-medium text-gray-700">
            Category
          </label>
          <select
            id="category"
            className={selectClass}
            {...register("category")}
          >
            <option value="">Select category</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
          {errors.category?.message && (
            <p className="text-sm text-red-600">{errors.category.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="difficulty" className="block text-sm font-medium text-gray-700">
            Difficulty
          </label>
          <select
            id="difficulty"
            className={selectClass}
            {...register("difficulty")}
          >
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {errors.difficulty?.message && (
            <p className="text-sm text-red-600">{errors.difficulty.message}</p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <span className="block text-sm font-medium text-gray-700">Muscle groups</span>
        <div className="flex flex-wrap gap-2">
          {MUSCLE_GROUP_OPTIONS.map((group) => {
            const active = selectedMuscles.includes(group);
            return (
              <button
                key={group}
                type="button"
                onClick={() => toggleMuscle(group)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }`}
                aria-pressed={active}
              >
                {group
                  .split("_")
                  .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </button>
            );
          })}
        </div>
        {muscleFields.length > 0 && (
          <div className="space-y-2">
            {muscleFields.map((field, index) => (
              <div key={field.id} className="flex items-center gap-2">
                <Input
                  placeholder="Custom muscle group"
                  {...register(`muscle_groups.${index}`)}
                  className="flex-1"
                />
                <button
                  type="button"
                  onClick={() => removeMuscle(index)}
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-red-600"
                  aria-label="Remove muscle group"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={() => appendMuscle("")}
          className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          <Plus className="h-4 w-4" /> Add custom muscle group
        </button>
      </div>

      <div className="space-y-2">
        <span className="block text-sm font-medium text-gray-700">Equipment needed</span>
        <div className="flex flex-wrap gap-2">
          {EQUIPMENT_OPTIONS.map((equipment) => {
            const active = selectedEquipment.includes(equipment);
            return (
              <button
                key={equipment}
                type="button"
                onClick={() => toggleEquipment(equipment)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }`}
                aria-pressed={active}
              >
                {equipment
                  .split(" ")
                  .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </button>
            );
          })}
        </div>
        {equipmentFields.length > 0 && (
          <div className="space-y-2">
            {equipmentFields.map((field, index) => (
              <div key={field.id} className="flex items-center gap-2">
                <Input
                  placeholder="Custom equipment"
                  {...register(`equipment_needed.${index}`)}
                  className="flex-1"
                />
                <button
                  type="button"
                  onClick={() => removeEquipment(index)}
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-red-600"
                  aria-label="Remove equipment"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={() => appendEquipment("")}
          className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          <Plus className="h-4 w-4" /> Add custom equipment
        </button>
      </div>

      <div className="space-y-2">
        <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <ListOrdered className="h-4 w-4" /> Instructions
        </span>
        {instructionFields.map((field, index) => (
          <div key={field.id} className="flex items-start gap-2">
            <span className="mt-2.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
              {index + 1}
            </span>
            <Input
              placeholder={`Step ${index + 1}`}
              {...register(`instructions.${index}`)}
              className="flex-1"
            />
            <button
              type="button"
              onClick={() => removeInstruction(index)}
              className="mt-2 rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-red-600"
              aria-label="Remove step"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => appendInstruction("")}
          className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          <Plus className="h-4 w-4" /> Add step
        </button>
      </div>

      <Input
        label="Media URL"
        type="url"
        placeholder="https://example.com/video.mp4"
        icon={<Link2 className="h-4 w-4" />}
        error={errors.media_url?.message}
        {...register("media_url")}
      />

      <div className="space-y-1.5">
        <label htmlFor="tips" className="block text-sm font-medium text-gray-700">
          Tips
        </label>
        <textarea
          id="tips"
          rows={3}
          placeholder="Coaching tips for this exercise"
          {...register("tips")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.tips?.message && (
          <p className="text-sm text-red-600">{errors.tips.message}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="contraindications" className="block text-sm font-medium text-gray-700">
          Contraindications
        </label>
        <textarea
          id="contraindications"
          rows={3}
          placeholder="When to avoid this exercise"
          {...register("contraindications")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        {errors.contraindications?.message && (
          <p className="text-sm text-red-600">{errors.contraindications.message}</p>
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
