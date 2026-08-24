"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { BranchForm } from "@/features/branches/components/BranchForm";
import { createBranch, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { BranchFormData } from "@/types/branch";

export default function NewBranchPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const handleSubmit = async (data: BranchFormData) => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/branches/new");
      return;
    }
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      const branch = await createBranch(data, authToken);
      toast.success("Branch created");
      router.push(`/branches/${branch.id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Add branch">
      <BranchForm
        submitLabel="Create branch"
        onSubmit={handleSubmit}
        error={error}
        loading={saving}
      />
    </DashboardLayout>
  );
}
