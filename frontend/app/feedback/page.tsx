"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BarChart3, Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { FeedbackTable } from "@/features/feedback/components/FeedbackTable";
import { Button, Alert, Spinner } from "@/components/ui";
import {
  fetchFeedback,
  respondToFeedback,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Feedback, FeedbackCategory } from "@/types/feedback";
import { CATEGORY_OPTIONS, getCategoryLabel } from "@/features/feedback/components/feedbackHelpers";

export default function FeedbackPage() {
  const router = useRouter();
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [respondingId, setRespondingId] = useState<number | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<FeedbackCategory | "">("");
  const [ratingFilter, setRatingFilter] = useState<string>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/feedback")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/feedback");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchFeedback(authToken);
        setFeedback(res.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/feedback/new") : false;

  const handleRespond = async (item: Feedback, response: string) => {
    const token = getToken();
    if (!token) return;
    setRespondingId(item.id);
    setError(null);
    try {
      const updated = await respondToFeedback(item.id, { response }, token);
      setFeedback((prev) =>
        prev.map((f) => (f.id === updated.id ? updated : f)),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRespondingId(null);
    }
  };

  const filtered = feedback.filter((f) => {
    if (categoryFilter && f.category !== categoryFilter) return false;
    if (ratingFilter && String(f.rating) !== ratingFilter) return false;
    if (dateFrom && new Date(f.created_at) < new Date(dateFrom)) return false;
    if (dateTo) {
      const to = new Date(dateTo);
      to.setHours(23, 59, 59, 999);
      if (new Date(f.created_at) > to) return false;
    }
    return true;
  });

  return (
    <DashboardLayout
      title="Feedback"
      actions={
        <div className="flex items-center gap-2">
          <Link href="/feedback/analytics">
            <Button variant="outline" size="sm">
              <BarChart3 className="h-4 w-4" /> Analytics
            </Button>
          </Link>
          {canCreate && (
            <Link href="/feedback/new">
              <Button size="sm">
                <Plus className="h-4 w-4" /> New feedback
              </Button>
            </Link>
          )}
        </div>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}

      {/* Filters */}
      <div className="mb-6 grid grid-cols-1 gap-4 rounded-xl border border-gray-200 bg-white p-4 md:grid-cols-4">
        <div className="space-y-1.5">
          <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700">
            Category
          </label>
          <select
            id="category-filter"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as FeedbackCategory | "")}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">All categories</option>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {getCategoryLabel(c)}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="rating-filter" className="block text-sm font-medium text-gray-700">
            Rating
          </label>
          <select
            id="rating-filter"
            value={ratingFilter}
            onChange={(e) => setRatingFilter(e.target.value)}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">All ratings</option>
            {[5, 4, 3, 2, 1].map((r) => (
              <option key={r} value={r}>
                {r} star{r > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="date-from" className="block text-sm font-medium text-gray-700">
            From
          </label>
          <input
            id="date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="date-to" className="block text-sm font-medium text-gray-700">
            To
          </label>
          <input
            id="date-to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}

      {!loading && (
        <FeedbackTable
          feedback={filtered}
          onRespond={handleRespond}
          respondingId={respondingId}
        />
      )}
    </DashboardLayout>
  );
}
