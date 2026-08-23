"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { TrainerForm } from "@/features/trainers/components/TrainerForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchTrainer, updateTrainer, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Trainer, TrainerFormData } from "@/types/trainer";

export default function EditTrainerPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [trainer, setTrainer] = useState<Trainer | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchTrainer(id, authToken);
        setTrainer(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const handleSubmit = async (data: TrainerFormData) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      await updateTrainer(id, data, authToken);
      toast.success("Trainer updated");
      router.push(`/trainers/${id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Edit trainer">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !trainer && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && trainer && (
        <TrainerForm
          trainer={trainer}
          submitLabel="Save changes"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
