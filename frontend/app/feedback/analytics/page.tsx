"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { FeedbackAnalyticsDashboard } from "@/features/feedback/components/FeedbackAnalyticsDashboard";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchFeedbackAnalytics, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { FeedbackAnalytics } from "@/types/feedback";

export default function FeedbackAnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<FeedbackAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/feedback/analytics")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/feedback/analytics");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchFeedbackAnalytics(authToken);
        setData(res);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  return (
    <DashboardLayout
      title="Feedback Analytics"
      actions={
        <Link href="/feedback">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4" /> Back to feedback
          </Button>
        </Link>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && <FeedbackAnalyticsDashboard data={data} />}
    </DashboardLayout>
  );
}
