"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Pencil, HeartPulse } from "lucide-react";
import { Button, Input, Alert, Badge } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type { BloodGroup, HealthProfile, HealthProfileUpdate } from "@/types/customer-detail";
import { BLOOD_GROUP_OPTIONS } from "@/types/customer-detail";

const healthSchema = z.object({
  height_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  weight_kg: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  blood_group: z.enum(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]),
});

type HealthSchemaData = z.infer<typeof healthSchema>;

/** Render a list of string tags as chips, or an em dash when empty. */
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
    formState: { errors },
  } = useForm<HealthSchemaData>({
    resolver: zodResolver(healthSchema),
    defaultValues: {
      height_cm: undefined,
      weight_kg: undefined,
      blood_group: "unknown",
    },
  });

  const handleSave = async (data: HealthSchemaData) => {
    await onSave({
      height_cm: data.height_cm,
      weight_kg: data.weight_kg,
      blood_group: data.blood_group,
    });
    setEditMode(false);
  };

  const beginEdit = () => {
    if (profile) {
      reset({
        height_cm: profile.height_cm != null ? Number(profile.height_cm) : undefined,
        weight_kg: profile.weight_kg != null ? Number(profile.weight_kg) : undefined,
        blood_group: profile.blood_group || "unknown",
      });
    }
    setEditMode(true);
  };

  if (loading) return <p className="text-sm text-gray-500">Loading health profile…</p>;

  if (!profile) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
        <HeartPulse className="mx-auto mb-2 h-6 w-6 text-gray-300" />
        <p className="text-sm text-gray-500">No health profile on file yet.</p>
        {!editMode && (
          <Button size="sm" variant="outline" className="mt-4" onClick={() => setEditMode(true)}>
            <Pencil className="h-4 w-4" /> Add health profile
          </Button>
        )}
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

      {!editMode ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Vitals</p>
            <dl className="space-y-2 text-sm">
              <Row label="Height" value={profile.height_cm != null ? `${profile.height_cm} cm` : "—"} />
              <Row label="Weight" value={profile.weight_kg != null ? `${profile.weight_kg} kg` : "—"} />
              <Row label="BMI" value={profile.bmi != null ? String(profile.bmi) : "—"} />
              <Row label="Blood group" value={profile.blood_group || "—"} />
            </dl>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Medical</p>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Medical conditions</dt>
                <dd><TagList items={profile.medical_conditions} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Allergies</dt>
                <dd><TagList items={profile.allergies} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Food allergies</dt>
                <dd><TagList items={profile.food_allergies} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Medications</dt>
                <dd><TagList items={profile.medications} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Dietary restrictions</dt>
                <dd><TagList items={profile.dietary_restrictions} /></dd>
              </div>
            </dl>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-sm font-medium text-gray-700">Injuries</p>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Current injuries</dt>
                <dd><TagList items={profile.current_injuries} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Past injuries</dt>
                <dd><TagList items={profile.past_injuries} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Injury notes</dt>
                <dd className="text-gray-700">{profile.injuries || "—"}</dd>
              </div>
            </dl>
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit(handleSave)}
          className="max-w-xl space-y-4 rounded-xl border border-gray-200 bg-white p-5"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
          </div>
          <div className="space-y-1.5">
            <label htmlFor="blood_group" className="block text-sm font-medium text-gray-700">
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
