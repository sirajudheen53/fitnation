"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Pencil, HeartPulse, Plus, X } from "lucide-react";
import { Button, Input, Alert, Badge } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type {
  BloodGroup,
  HealthProfile,
  HealthProfileUpdate,
} from "@/types/customer-detail";
import { BLOOD_GROUP_OPTIONS } from "@/types/customer-detail";

/* ── Tag-input helper ──────────────────────────────────────────── */

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  label?: string;
}

export function TagInput({ value, onChange, placeholder = "Add…", label }: TagInputProps) {
  const [input, setInput] = useState("");

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput("");
  };

  const removeTag = (tag: string) => {
    onChange(value.filter((t) => t !== tag));
  };

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-gray-700">{label}</label>
      )}
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 focus-within:border-brand-500 focus-within:outline-none focus-within:ring-1 focus-within:ring-brand-500">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              className="flex h-3 w-3 items-center justify-center rounded-full hover:bg-brand-200"
            >
              <X className="h-2.5 w-2.5" />
            </button>
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              addTag();
            }
            if (e.key === "Backspace" && !input && value.length > 0) {
              removeTag(value[value.length - 1]);
            }
          }}
          onBlur={addTag}
          placeholder={value.length === 0 ? placeholder : ""}
          className="min-w-24 flex-1 bg-transparent text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none"
        />
      </div>
    </div>
  );
}

/* ── Read-only tag list ────────────────────────────────────────── */

export function TagList({ items }: { items: string[] | undefined }) {
  if (!items || items.length === 0) return <span className="text-gray-400">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <Badge key={i} variant="default">
          {item}
        </Badge>
      ))}
    </div>
  );
}

/* ── Edit schema ──────────────────────────────────────────────── */

const healthSchema = z.object({
  height_cm: z.coerce
    .number()
    .positive()
    .optional()
    .or(z.nan().transform(() => undefined)),
  weight_kg: z.coerce
    .number()
    .positive()
    .optional()
    .or(z.nan().transform(() => undefined)),
  blood_group: z.enum(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]),
  injuries: z.string().max(1000).optional().or(z.literal("")),
  current_injuries: z.array(z.string()).optional().default([]),
  past_injuries: z.array(z.string()).optional().default([]),
  medical_conditions: z.array(z.string()).optional().default([]),
  allergies: z.array(z.string()).optional().default([]),
  food_allergies: z.array(z.string()).optional().default([]),
  medications: z.array(z.string()).optional().default([]),
  dietary_restrictions: z.array(z.string()).optional().default([]),
});

type HealthSchemaData = z.infer<typeof healthSchema>;

/* ── Component ────────────────────────────────────────────────── */

interface HealthProfileTabProps {
  profile: HealthProfile | null;
  loading?: boolean;
  saving?: boolean;
  error?: unknown;
  onSave: (data: HealthProfileUpdate) => void | Promise<void>;
}

export function HealthProfileTab({
  profile,
  loading = false,
  saving = false,
  error,
  onSave,
}: HealthProfileTabProps) {
  const [editMode, setEditMode] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<HealthSchemaData>({
    resolver: zodResolver(healthSchema),
  });

  const watchedFields = watch();

  const handleSave = async (data: HealthSchemaData) => {
    await onSave({
      height_cm: data.height_cm,
      weight_kg: data.weight_kg,
      blood_group: data.blood_group,
      injuries: data.injuries,
      current_injuries: data.current_injuries,
      past_injuries: data.past_injuries,
      medical_conditions: data.medical_conditions,
      allergies: data.allergies,
      food_allergies: data.food_allergies,
      medications: data.medications,
      dietary_restrictions: data.dietary_restrictions,
    });
    setEditMode(false);
  };

  const beginEdit = () => {
    if (profile) {
      reset({
        height_cm: profile.height_cm != null ? Number(profile.height_cm) : undefined,
        weight_kg: profile.weight_kg != null ? Number(profile.weight_kg) : undefined,
        blood_group: profile.blood_group || "unknown",
        injuries: profile.injuries || "",
        current_injuries: profile.current_injuries ?? [],
        past_injuries: profile.past_injuries ?? [],
        medical_conditions: profile.medical_conditions ?? [],
        allergies: profile.allergies ?? [],
        food_allergies: profile.food_allergies ?? [],
        medications: profile.medications ?? [],
        dietary_restrictions: profile.dietary_restrictions ?? [],
      });
    }
    setEditMode(true);
  };

  if (loading) return <p className="text-sm text-gray-500">Loading health profile…</p>;

  if (!profile && !editMode) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
        <HeartPulse className="mx-auto mb-2 h-6 w-6 text-gray-300" />
        <p className="text-sm text-gray-500">No health profile on file yet.</p>
        <Button
          size="sm"
          variant="outline"
          className="mt-4"
          onClick={() => setEditMode(true)}
        >
          <Pencil className="h-4 w-4" /> Add health profile
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Health profile</h3>
        {!editMode && (
          <Button size="sm" variant="outline" onClick={beginEdit}>
            <Pencil className="h-4 w-4" /> Edit
          </Button>
        )}
      </div>

      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      {/* Read-only view */}
      {!editMode && profile && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Vitals */}
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Vitals</p>
            <dl className="space-y-2 text-sm">
              <Row
                label="Height"
                value={profile.height_cm != null ? `${profile.height_cm} cm` : "—"}
              />
              <Row
                label="Weight"
                value={profile.weight_kg != null ? `${profile.weight_kg} kg` : "—"}
              />
              <Row label="BMI" value={profile.bmi != null ? String(profile.bmi) : "—"} />
              <Row
                label="Blood group"
                value={profile.blood_group === "unknown" ? "—" : profile.blood_group}
              />
            </dl>
          </div>

          {/* Medical */}
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Medical</p>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Medical conditions</dt>
                <dd className="mt-1">
                  <TagList items={profile.medical_conditions} />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Allergies</dt>
                <dd className="mt-1">
                  <TagList items={profile.allergies} />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Food allergies</dt>
                <dd className="mt-1">
                  <TagList items={profile.food_allergies} />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Medications</dt>
                <dd className="mt-1">
                  <TagList items={profile.medications} />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Dietary restrictions</dt>
                <dd className="mt-1">
                  <TagList items={profile.dietary_restrictions} />
                </dd>
              </div>
            </dl>
          </div>

          {/* Injuries */}
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Injuries</p>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Current injuries</dt>
                <dd className="mt-1">
                  <TagList items={profile.current_injuries} />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Past injuries</dt>
                <dd className="mt-1">
                  <TagList items={profile.past_injuries} />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Injury notes</dt>
                <dd className="mt-1 text-gray-700">{profile.injuries || "—"}</dd>
              </div>
            </dl>
          </div>

          {/* Emergency contact */}
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Emergency contact</p>
            <dl className="space-y-2 text-sm">
              <Row label="Contact name" value={profile.medical_info?.emergency_contact_name as string || "—"} />
              <Row label="Phone" value={profile.medical_info?.emergency_contact_phone as string || "—"} />
            </dl>
          </div>
        </div>
      )}

      {/* Edit form */}
      {editMode && (
        <form
          onSubmit={handleSubmit(handleSave)}
          className="space-y-6 rounded-xl border border-gray-200 bg-white p-5"
        >
          {/* Vitals */}
          <div>
            <p className="mb-3 text-sm font-medium text-gray-700">Vitals</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input
                label="Height (cm)"
                type="number"
                placeholder="e.g. 172"
                error={errors.height_cm?.message}
                {...register("height_cm")}
              />
              <Input
                label="Weight (kg)"
                type="number"
                placeholder="e.g. 75"
                error={errors.weight_kg?.message}
                {...register("weight_kg")}
              />
              <div className="space-y-1.5">
                <label
                  htmlFor="blood_group"
                  className="block text-sm font-medium text-gray-700"
                >
                  Blood group
                </label>
                <select
                  id="blood_group"
                  {...register("blood_group")}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
                >
                  {BLOOD_GROUP_OPTIONS.map((bg: BloodGroup) => (
                    <option key={bg} value={bg}>
                      {bg === "unknown" ? "Unknown" : bg}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Medical conditions */}
          <div>
            <p className="mb-3 text-sm font-medium text-gray-700">Medical</p>
            <div className="space-y-3">
              <TagInput
                label="Medical conditions"
                value={watchedFields.medical_conditions ?? []}
                onChange={(tags) => setValue("medical_conditions", tags, { shouldValidate: true })}
                placeholder="e.g. Hypertension, Diabetes"
              />
              <TagInput
                label="Allergies"
                value={watchedFields.allergies ?? []}
                onChange={(tags) => setValue("allergies", tags, { shouldValidate: true })}
                placeholder="e.g. Penicillin, Pollen"
              />
              <TagInput
                label="Food allergies"
                value={watchedFields.food_allergies ?? []}
                onChange={(tags) => setValue("food_allergies", tags, { shouldValidate: true })}
                placeholder="e.g. Gluten, Dairy"
              />
              <TagInput
                label="Medications"
                value={watchedFields.medications ?? []}
                onChange={(tags) => setValue("medications", tags, { shouldValidate: true })}
                placeholder="e.g. Metformin, Lisinopril"
              />
              <TagInput
                label="Dietary restrictions"
                value={watchedFields.dietary_restrictions ?? []}
                onChange={(tags) => setValue("dietary_restrictions", tags, { shouldValidate: true })}
                placeholder="e.g. Vegan, Kosher"
              />
            </div>
          </div>

          {/* Injuries */}
          <div>
            <p className="mb-3 text-sm font-medium text-gray-700">Injuries</p>
            <div className="space-y-3">
              <TagInput
                label="Current injuries"
                value={watchedFields.current_injuries ?? []}
                onChange={(tags) => setValue("current_injuries", tags, { shouldValidate: true })}
                placeholder="e.g. Ankle sprain, Lower back pain"
              />
              <TagInput
                label="Past injuries"
                value={watchedFields.past_injuries ?? []}
                onChange={(tags) => setValue("past_injuries", tags, { shouldValidate: true })}
                placeholder="e.g. ACL tear (2023), Shoulder dislocation"
              />
              <div className="space-y-1.5">
                <label
                  htmlFor="injuries"
                  className="block text-sm font-medium text-gray-700"
                >
                  Injury notes
                </label>
                <textarea
                  id="injuries"
                  rows={3}
                  placeholder="Additional notes about injuries, surgeries, or physical limitations"
                  {...register("injuries")}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <Button type="submit" loading={saving}>
              Save health profile
            </Button>
            <Button type="button" variant="outline" onClick={() => setEditMode(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-gray-900">{value}</dd>
    </div>
  );
}
