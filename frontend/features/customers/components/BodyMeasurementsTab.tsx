"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Ruler } from "lucide-react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { Button, Input, Alert } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type { BodyMeasurement, BodyMeasurementFormData } from "@/types/customer-detail";

/** Map a list of measurements to chart points (weight + BMI by date). */
export function measurementChartData(
  measurements: BodyMeasurement[],
): { date: string; weight: number | null; bmi: number | null }[] {
  return [...measurements]
    .sort((a, b) => a.date_logged.localeCompare(b.date_logged))
    .map((m) => ({
      date: formatMeasurementDate(m.date_logged),
      weight: m.weight_kg != null ? Number(m.weight_kg) : null,
      bmi: m.bmi != null ? Number(m.bmi) : null,
    }));
}

/** Format a YYYY-MM-DD date to a short label. */
export function formatMeasurementDate(date: string): string {
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

/** Format a numeric field for display, or em dash when null/empty. */
export function formatNum(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

const measurementSchema = z.object({
  weight_kg: z.coerce.number().min(1, "Weight must be greater than 0").max(500),
  body_fat_percentage: z.coerce.number().min(0).max(100).optional().or(z.nan().transform(() => undefined)),
  chest_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  waist_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  hips_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  biceps_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  thighs_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
  neck_cm: z.coerce.number().positive().optional().or(z.nan().transform(() => undefined)),
});

type MeasurementSchemaData = z.infer<typeof measurementSchema>;

interface BodyMeasurementsTabProps {
  measurements: BodyMeasurement[];
  loading?: boolean;
  saving?: boolean;
  error?: unknown;
  onAdd: (data: BodyMeasurementFormData) => void | Promise<void>;
}

export function BodyMeasurementsTab({
  measurements,
  loading = false,
  saving = false,
  error,
  onAdd,
}: BodyMeasurementsTabProps) {
  const [showForm, setShowForm] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<MeasurementSchemaData>({
    resolver: zodResolver(measurementSchema),
    defaultValues: {
      weight_kg: undefined,
      body_fat_percentage: undefined,
      chest_cm: undefined,
      waist_cm: undefined,
      hips_cm: undefined,
      biceps_cm: undefined,
      thighs_cm: undefined,
      neck_cm: undefined,
    },
  });

  const chartData = measurementChartData(measurements);

  const handleAdd = async (data: MeasurementSchemaData) => {
    await onAdd({
      weight_kg: data.weight_kg,
      body_fat_percentage: data.body_fat_percentage,
      chest_cm: data.chest_cm,
      waist_cm: data.waist_cm,
      hips_cm: data.hips_cm,
      biceps_cm: data.biceps_cm,
      thighs_cm: data.thighs_cm,
      neck_cm: data.neck_cm,
    });
    reset();
    setShowForm(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Body measurements</h3>
        <Button size="sm" variant="outline" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" /> {showForm ? "Cancel" : "Add measurement"}
        </Button>
      </div>

      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {loading && <p className="text-sm text-gray-500">Loading measurements…</p>}

      {!loading && measurements.length === 0 && !showForm && (
        <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
          <Ruler className="mx-auto mb-2 h-6 w-6 text-gray-300" />
          <p className="text-sm text-gray-500">No body measurements recorded yet.</p>
        </div>
      )}

      {chartData.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="mb-2 text-sm font-medium text-gray-700">Weight over time (kg)</p>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="weight"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="mb-2 text-sm font-medium text-gray-700">BMI over time</p>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="bmi"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {!loading && measurements.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Date</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Weight</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">BMI</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Waist</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Chest</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Body fat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {measurements.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-900">
                    {formatMeasurementDate(m.date_logged)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatNum(m.weight_kg)} kg
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">{formatNum(m.bmi)}</td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatNum(m.waist_cm)} cm
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatNum(m.chest_cm)} cm
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatNum(m.body_fat_percentage)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && showForm && (
        <form
          onSubmit={handleSubmit(handleAdd)}
          className="space-y-4 rounded-xl border border-gray-200 bg-white p-4"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Weight (kg) *"
              type="number"
              placeholder="e.g. 75"
              error={errors.weight_kg?.message}
              {...register("weight_kg")}
            />
            <Input
              label="Body fat (%)"
              type="number"
              placeholder="e.g. 18"
              error={errors.body_fat_percentage?.message}
              {...register("body_fat_percentage")}
            />
            <Input
              label="Waist (cm)"
              type="number"
              placeholder="e.g. 82"
              error={errors.waist_cm?.message}
              {...register("waist_cm")}
            />
            <Input
              label="Chest (cm)"
              type="number"
              placeholder="e.g. 98"
              error={errors.chest_cm?.message}
              {...register("chest_cm")}
            />
            <Input
              label="Hips (cm)"
              type="number"
              placeholder="e.g. 96"
              error={errors.hips_cm?.message}
              {...register("hips_cm")}
            />
            <Input
              label="Biceps (cm)"
              type="number"
              placeholder="e.g. 34"
              error={errors.biceps_cm?.message}
              {...register("biceps_cm")}
            />
            <Input
              label="Thighs (cm)"
              type="number"
              placeholder="e.g. 58"
              error={errors.thighs_cm?.message}
              {...register("thighs_cm")}
            />
            <Input
              label="Neck (cm)"
              type="number"
              placeholder="e.g. 38"
              error={errors.neck_cm?.message}
              {...register("neck_cm")}
            />
          </div>

          <Button type="submit" loading={saving}>
            Save measurement
          </Button>
        </form>
      )}
    </div>
  );
}
