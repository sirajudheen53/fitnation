"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AssignmentForm } from "@/features/trainers/components/AssignmentForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchTrainers, fetchCustomers, assignTrainer, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { AssignmentFormData } from "@/types/trainer";
import type { Trainer } from "@/types/trainer";
import type { Customer } from "@/types/customer";

export default function AssignTrainerPage() {
  const router = useRouter();
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers/assign");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const [trainerRes, customerRes] = await Promise.all([
          fetchTrainers(authToken),
          fetchCustomers(authToken),
        ]);
        setTrainers(trainerRes.results);
        setCustomers(customerRes.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  const handleSubmit = async (data: AssignmentFormData) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      await assignTrainer(data, authToken);
      toast.success("Trainer assigned");
      router.push("/trainers");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Assign trainer">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && trainers.length === 0 && (
        <Alert variant="info">No trainers available to assign.</Alert>
      )}
      {!loading && trainers.length > 0 && (
        <AssignmentForm
          trainers={trainers}
          customers={customers}
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
