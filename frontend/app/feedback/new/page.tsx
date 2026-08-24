"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { FeedbackForm } from "@/features/feedback/components/FeedbackForm";
import { createFeedback, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { FeedbackFormData } from "@/types/feedback";

export default function FeedbackCreatePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const storedUser =
      typeof window !== "undefined" ? localStorage.getItem("fbos_user") : null;
    const role = storedUser ? (JSON.parse(storedUser).role as string) : null;
    if (role && !canAccessRoute(role, "/feedback/new")) {
      router.replace("/unauthorized");
    }
  }, [router]);

  const handleSubmit = async (data: FeedbackFormData) => {
    const token = getToken();
    if (!token) {
      setError("Authentication token not found.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await createFeedback(data, token);
      router.push("/feedback");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout title="New Feedback">
      <FeedbackForm
        onSubmit={handleSubmit}
        submitLabel="Submit feedback"
        error={error}
        loading={loading}
      />
    </DashboardLayout>
  );
}
