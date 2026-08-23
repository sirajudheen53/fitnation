"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CheckInForm } from "@/features/attendance/components/CheckInForm";
import { Alert } from "@/components/ui";
import { checkIn, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { CheckInData } from "@/types/attendance";

export default function CheckInPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState<{ person_name: string; check_in_time: string } | null>(null);

  const handleSubmit = async (data: CheckInData) => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/attendance/check-in");
      return;
    }
    const authToken: string = token;
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const record = await checkIn(data, authToken);
      setSuccess({
        person_name: record.person_name,
        check_in_time: record.check_in_time ?? "—",
      });
      toast.success(`${record.person_name} checked in`);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout title="Check in">
      {success && (
        <Alert variant="success">
          <strong>{success.person_name}</strong> checked in at{" "}
          {new Date(success.check_in_time).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </Alert>
      )}
      <CheckInForm onSubmit={handleSubmit} error={error} loading={loading} />
    </DashboardLayout>
  );
}
