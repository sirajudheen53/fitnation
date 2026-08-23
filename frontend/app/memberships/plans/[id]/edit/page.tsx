"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { MembershipPlanForm } from "@/features/memberships/components/MembershipPlanForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchMembershipPlan, updateMembershipPlan, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { MembershipPlan, MembershipPlanFormData } from "@/types/membership";

export default function EditMembershipPlanPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [plan, setPlan] = useState<MembershipPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/memberships");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchMembershipPlan(id, authToken);
        setPlan(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const handleSubmit = async (data: MembershipPlanFormData) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      await updateMembershipPlan(id, data, authToken);
      toast.success("Membership plan updated");
      router.push("/memberships");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Edit membership plan">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !plan && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && plan && (
        <MembershipPlanForm
          plan={plan}
          submitLabel="Save changes"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
