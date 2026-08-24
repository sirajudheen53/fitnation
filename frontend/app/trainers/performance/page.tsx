"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, TrendingUp } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  PerformanceTable,
  filterRows,
  sortRows,
  uniqueSpecializations,
  type SortDirection,
  type SortKey,
} from "@/features/trainers/components/PerformanceTable";
import { Alert, Spinner, Input } from "@/components/ui";
import {
  fetchTrainerPerformance,
  fetchTrainers,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Trainer } from "@/types/trainer";
import type { TrainerPerformanceRow } from "@/types/trainer-performance";

export default function TrainerPerformancePage() {
  const router = useRouter();
  const [rows, setRows] = useState<TrainerPerformanceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [specialization, setSpecialization] = useState("all");
  const [minRating, setMinRating] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("revenue");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/trainers")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers/performance");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [perfRes, trainerRes] = await Promise.all([
          fetchTrainerPerformance(authToken),
          fetchTrainers(authToken),
        ]);

        const trainers: Trainer[] = Array.isArray(trainerRes)
          ? trainerRes
          : trainerRes.results ?? [];

        // Latest snapshot per trainer, keyed by trainer id.
        const latestByTrainer = new Map<number, (typeof perfRes)[number]>();
        perfRes.forEach((rec) => {
          const existing = latestByTrainer.get(rec.trainer);
          if (!existing || rec.month > existing.month) latestByTrainer.set(rec.trainer, rec);
        });

        const joined: TrainerPerformanceRow[] = trainers.map((t) => {
          const latest = latestByTrainer.get(t.id);
          return {
            trainer_id: t.id,
            name: `${t.first_name} ${t.last_name}`.trim() || t.email,
            specialization: t.specialization,
            rating: latest && latest.rating_avg !== null ? Number(latest.rating_avg) : null,
            assigned_customers: latest?.customer_count ?? t.active_clients ?? 0,
            active_plans: 0,
            attendance_rate: null,
            revenue: latest ? Number(latest.revenue) || 0 : Number(t.revenue) || 0,
            sessions_completed: latest?.sessions_completed ?? 0,
          };
        });

        setRows(joined);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const specializations = useMemo(() => uniqueSpecializations(rows), [rows]);

  const filtered = useMemo(() => {
    let result = filterRows(rows, {
      specialization: specialization === "all" ? undefined : specialization,
      minRating: minRating || undefined,
    });
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (r) => r.name.toLowerCase().includes(q) || (r.specialization ?? "").toLowerCase().includes(q),
      );
    }
    return sortRows(result, sortKey, sortDirection);
  }, [rows, search, specialization, minRating, sortKey, sortDirection]);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection(key === "name" || key === "specialization" ? "asc" : "desc");
    }
  };

  return (
    <DashboardLayout title="Trainer performance">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <Input
            placeholder="Search by trainer name"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            aria-label="Search trainers"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={specialization}
            onChange={(e) => setSpecialization(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
            aria-label="Filter by specialization"
          >
            <option value="all">All specializations</option>
            {specializations.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={minRating}
            onChange={(e) => setMinRating(Number(e.target.value))}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
            aria-label="Filter by minimum rating"
          >
            <option value={0}>Any rating</option>
            <option value={3}>3+ stars</option>
            <option value={4}>4+ stars</option>
            <option value={4.5}>4.5+ stars</option>
          </select>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && rows.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <TrendingUp className="mx-auto mb-3 h-8 w-8 text-gray-300" />
          <p className="text-sm text-gray-500">
            No trainer performance data yet. Performance snapshots will appear here once trainers
            have activity.
          </p>
        </div>
      )}
      {!loading && rows.length > 0 && filtered.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No trainers match your filters.</p>
        </div>
      )}
      {!loading && filtered.length > 0 && (
        <PerformanceTable
          rows={filtered}
          sortKey={sortKey}
          sortDirection={sortDirection}
          onSort={handleSort}
        />
      )}
    </DashboardLayout>
  );
}
