"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { MembershipPlanForm } from "@/features/memberships/components/MembershipPlanForm";
import { createMembershipPlan, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { MembershipPlanFormData } from "@/types/membership";

export default function NewMembershipPlanPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const handleSubmit = async (data: MembershipPlanFormData) => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/memberships/plans/new");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await createMembershipPlan(data, token);
      toast.success("Membership plan created");
      router.push("/memberships");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout title="New membership plan">
      <MembershipPlanForm
        submitLabel="Create plan"
        onSubmit={handleSubmit}
        error={error}
        loading={loading}
      />
    </DashboardLayout>
  );
}
