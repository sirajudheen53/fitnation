"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { BranchForm } from "@/features/branches/components/BranchForm";
import { Spinner, Alert } from "@/components/ui";
import { fetchBranch, updateBranch, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Branch, BranchFormData } from "@/types/branch";

export default function EditBranchPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [branch, setBranch] = useState<Branch | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/branches");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchBranch(id, authToken);
        setBranch(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const handleSubmit = async (data: BranchFormData) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      await updateBranch(id, data, authToken);
      toast.success("Branch updated");
      router.push(`/branches/${id}`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Edit branch">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !branch && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && branch && (
        <BranchForm
          branch={branch}
          submitLabel="Save changes"
          onSubmit={handleSubmit}
          error={error}
          loading={saving}
        />
      )}
    </DashboardLayout>
  );
}
