"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Camera, Columns2 } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type { ProgressPhoto, ProgressPhotoFormData } from "@/types/customer-detail";

const photoSchema = z.object({
  image: z.string().url("Enter a valid image URL").min(1, "Image URL is required"),
  caption: z.string().max(200).optional().or(z.literal("")),
});

type PhotoSchemaData = z.infer<typeof photoSchema>;

interface ProgressPhotosTabProps {
  photos: ProgressPhoto[];
  loading?: boolean;
  saving?: boolean;
  error?: unknown;
  onAdd: (data: ProgressPhotoFormData) => void | Promise<void>;
}

export function ProgressPhotosTab({
  photos,
  loading = false,
  saving = false,
  error,
  onAdd,
}: ProgressPhotosTabProps) {
  const [showForm, setShowForm] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [selected, setSelected] = useState<ProgressPhoto | null>(null);
  const [compareA, setCompareA] = useState<ProgressPhoto | null>(null);
  const [compareB, setCompareB] = useState<ProgressPhoto | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PhotoSchemaData>({
    resolver: zodResolver(photoSchema),
    defaultValues: { image: "", caption: "" },
  });

  const handleAdd = async (data: PhotoSchemaData) => {
    await onAdd({ image: data.image, caption: data.caption || undefined });
    reset();
    setShowForm(false);
  };

  const sorted = [...photos].sort((a, b) =>
    (a.taken_at ?? a.created_at).localeCompare(b.taken_at ?? b.created_at),
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Progress photos</h3>
        <div className="flex gap-2">
          {sorted.length >= 2 && (
            <Button size="sm" variant="outline" onClick={() => setCompareMode((v) => !v)}>
              <Columns2 className="h-4 w-4" /> {compareMode ? "Exit compare" : "Compare"}
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => setShowForm((v) => !v)}>
            <Plus className="h-4 w-4" /> {showForm ? "Cancel" : "Upload"}
          </Button>
        </div>
      </div>

      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {loading && <p className="text-sm text-gray-500">Loading photos…</p>}

      {!loading && photos.length === 0 && !showForm && (
        <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
          <Camera className="mx-auto mb-2 h-6 w-6 text-gray-300" />
          <p className="text-sm text-gray-500">No progress photos uploaded yet.</p>
        </div>
      )}

      {!loading && compareMode && sorted.length >= 2 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="mb-3 text-sm text-gray-600">
            Select two photos to compare side by side.
          </p>
          <div className="mb-3 grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="compare-a" className="mb-1 block text-xs text-gray-500">
                Before
              </label>
              <select
                id="compare-a"
                value={compareA?.id ?? ""}
                onChange={(e) =>
                  setCompareA(sorted.find((p) => p.id === Number(e.target.value)) ?? null)
                }
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Select…</option>
                {sorted.map((p) => (
                  <option key={p.id} value={p.id}>
                    {formatPhotoDate(p)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="compare-b" className="mb-1 block text-xs text-gray-500">
                After
              </label>
              <select
                id="compare-b"
                value={compareB?.id ?? ""}
                onChange={(e) =>
                  setCompareB(sorted.find((p) => p.id === Number(e.target.value)) ?? null)
                }
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Select…</option>
                {sorted.map((p) => (
                  <option key={p.id} value={p.id}>
                    {formatPhotoDate(p)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {(compareA || compareB) && (
            <div className="grid grid-cols-2 gap-3">
              {[compareA, compareB].map((p, i) => (
                <div key={i} className="overflow-hidden rounded-lg border border-gray-200">
                  {p ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={p.image}
                      alt={p.caption || "Progress photo"}
                      className="h-56 w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-56 items-center justify-center text-xs text-gray-400">
                      No photo selected
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!loading && !compareMode && photos.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {sorted.map((photo) => (
            <button
              key={photo.id}
              type="button"
              onClick={() => setSelected(photo)}
              className="group overflow-hidden rounded-lg border border-gray-200 text-left"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photo.image}
                alt={photo.caption || "Progress photo"}
                className="h-40 w-full object-cover transition-transform group-hover:scale-105"
              />
              <div className="p-2 text-xs text-gray-500">{formatPhotoDate(photo)}</div>
            </button>
          ))}
        </div>
      )}

      {!loading && showForm && (
        <form
          onSubmit={handleSubmit(handleAdd)}
          className="max-w-xl space-y-4 rounded-xl border border-gray-200 bg-white p-5"
        >
          <Input
            label="Image URL"
            placeholder="https://…/photo.jpg"
            error={errors.image?.message}
            {...register("image")}
          />
          <Input
            label="Caption (optional)"
            placeholder="Front view"
            error={errors.caption?.message}
            {...register("caption")}
          />
          <Button type="submit" loading={saving}>
            Upload photo
          </Button>
        </form>
      )}

      {selected && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={selected.caption || "Progress photo"}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setSelected(null)}
        >
          <div className="max-w-lg" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={selected.image}
              alt={selected.caption || "Progress photo"}
              className="max-h-[80vh] w-full rounded-lg object-contain"
            />
            <p className="mt-2 text-center text-sm text-white">
              {selected.caption || formatPhotoDate(selected)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function formatPhotoDate(photo: ProgressPhoto): string {
  const raw = photo.taken_at || photo.created_at;
  if (!raw) return "—";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}
