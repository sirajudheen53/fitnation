"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Star, Users, Wallet, CalendarCheck } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PerformanceMetricCard } from "@/features/trainers/components/PerformanceMetricCard";
import {
  PlansBarChart,
  TrendChart,
  monthlySeries,
} from "@/features/trainers/components/PerformanceCharts";
import { formatCurrency, formatRating } from "@/features/trainers/components/PerformanceTable";
import { Alert, Spinner } from "@/components/ui";
import { fetchTrainer, fetchTrainerPerformanceDetail, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Trainer } from "@/types/trainer";
import type { TrainerPerformanceDetail } from "@/types/trainer-performance";

export default function TrainerPerformanceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [trainer, setTrainer] = useState<Trainer | null>(null);
  const [performance, setPerformance] = useState<TrainerPerformanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
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
        const [t, p] = await Promise.all([
          fetchTrainer(id, authToken),
          fetchTrainerPerformanceDetail(id, authToken),
        ]);
        setTrainer(t);
        setPerformance(p);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const series = useMemo(
    () => (performance ? monthlySeries(performance.monthly_records) : []),
    [performance],
  );

  const revenueData = series.map((s) => ({ month: s.month, value: s.revenue }));
  const ratingData = series.map((s) => ({ month: s.month, value: s.rating }));
  const plansData = series.map((s) => ({ month: s.month, plans: s.plans }));

  const title = trainer ? `${trainer.first_name} ${trainer.last_name} — Performance` : "Performance";

  return (
    <DashboardLayout title={title}>
      <div className="mb-4">
        <Link
          href="/trainers/performance"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to performance
        </Link>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && !performance && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && performance && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <PerformanceMetricCard
              label="Total customers"
              value={String(performance.average_customer_count)}
              icon={<Users className="h-5 w-5" />}
              hint="Avg. monthly"
            />
            <PerformanceMetricCard
              label="Revenue this period"
              value={formatCurrency(performance.total_revenue)}
              icon={<Wallet className="h-5 w-5" />}
            />
            <PerformanceMetricCard
              label="Sessions completed"
              value={String(performance.total_sessions_completed)}
              icon={<CalendarCheck className="h-5 w-5" />}
            />
            <PerformanceMetricCard
              label="Avg. customer rating"
              value={formatRating(performance.average_rating)}
              icon={<Star className="h-5 w-5" />}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TrendChart
              title="Revenue trend"
              data={revenueData}
              color="#4f46e5"
              valueFormatter={(v) => `₹${v.toLocaleString("en-IN")}`}
            />
            <TrendChart
              title="Customer rating trend"
              data={ratingData}
              color="#f59e0b"
              valueFormatter={(v) => `${v.toFixed(1)}★`}
            />
          </div>

          <PlansBarChart data={plansData} />

          {trainer && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 text-sm">
              <p className="mb-1 font-medium text-gray-900">{trainer.first_name} {trainer.last_name}</p>
              {trainer.specialization && (
                <p className="text-gray-500">{trainer.specialization}</p>
              )}
              <p className="mt-1 text-gray-500">{trainer.email}</p>
            </div>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
