"use client";

import Link from "next/link";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { TrainerPerformanceRow } from "@/types/trainer-performance";

/** Format a number as rupees. */
export function formatCurrency(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

/** Format a rating to one decimal place, or an em dash when null. */
export function formatRating(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return num.toFixed(1);
}

/** Format an attendance rate as a percentage, or em dash when null. */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export type SortKey =
  | "name"
  | "specialization"
  | "assigned_customers"
  | "revenue"
  | "rating"
  | "sessions_completed";

export type SortDirection = "asc" | "desc";

/** Sort performance rows by a key and direction. */
export function sortRows(
  rows: TrainerPerformanceRow[],
  key: SortKey,
  direction: SortDirection,
): TrainerPerformanceRow[] {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    let av: number | string;
    let bv: number | string;
    switch (key) {
      case "name":
        av = a.name.toLowerCase();
        bv = b.name.toLowerCase();
        break;
      case "specialization":
        av = (a.specialization ?? "").toLowerCase();
        bv = (b.specialization ?? "").toLowerCase();
        break;
      default:
        av = Number(a[key]) || 0;
        bv = Number(b[key]) || 0;
    }
    if (av < bv) return direction === "asc" ? -1 : 1;
    if (av > bv) return direction === "asc" ? 1 : -1;
    return 0;
  });
  return sorted;
}

/** Filter rows by specialization and minimum rating. */
export function filterRows(
  rows: TrainerPerformanceRow[],
  filters: { specialization?: string; minRating?: number },
): TrainerPerformanceRow[] {
  return rows.filter((row) => {
    if (filters.specialization) {
      const spec = (row.specialization ?? "").toLowerCase();
      if (!spec.includes(filters.specialization.toLowerCase())) return false;
    }
    if (filters.minRating !== undefined && filters.minRating > 0) {
      if (row.rating === null || Number(row.rating) < filters.minRating) return false;
    }
    return true;
  });
}

/** Collect the set of specializations present across rows. */
export function uniqueSpecializations(rows: TrainerPerformanceRow[]): string[] {
  const set = new Set<string>();
  rows.forEach((r) => {
    if (r.specialization) set.add(r.specialization);
  });
  return Array.from(set).sort();
}

const COLUMN_LABELS: Record<SortKey, string> = {
  name: "Trainer",
  specialization: "Specialization",
  assigned_customers: "Customers",
  revenue: "Revenue",
  rating: "Rating",
  sessions_completed: "Sessions",
};

interface PerformanceTableProps {
  rows: TrainerPerformanceRow[];
  sortKey: SortKey;
  sortDirection: SortDirection;
  onSort: (key: SortKey) => void;
}

export function PerformanceTable({
  rows,
  sortKey,
  sortDirection,
  onSort,
}: PerformanceTableProps) {
  const renderHeader = (key: SortKey) => {
    const active = sortKey === key;
    const Icon = !active ? ArrowUpDown : sortDirection === "asc" ? ArrowUp : ArrowDown;
    return (
      <button
        type="button"
        onClick={() => onSort(key)}
        className={cn(
          "inline-flex items-center gap-1 font-medium hover:text-gray-900",
          active ? "text-brand-700" : "text-gray-500",
        )}
      >
        {COLUMN_LABELS[key]}
        <Icon className="h-3.5 w-3.5" />
      </button>
    );
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left">{renderHeader("name")}</th>
            <th className="px-4 py-3 text-left">{renderHeader("specialization")}</th>
            <th className="px-4 py-3 text-right">{renderHeader("assigned_customers")}</th>
            <th className="px-4 py-3 text-right">{renderHeader("revenue")}</th>
            <th className="px-4 py-3 text-right">{renderHeader("rating")}</th>
            <th className="px-4 py-3 text-right">{renderHeader("sessions_completed")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row) => (
            <tr key={row.trainer_id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <Link
                  href={`/trainers/${row.trainer_id}/performance`}
                  className="font-medium text-gray-900 hover:text-brand-700"
                >
                  {row.name}
                </Link>
              </td>
              <td className="px-4 py-3 text-gray-600">
                {row.specialization ? (
                  <Badge variant="default">{row.specialization}</Badge>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-4 py-3 text-right text-gray-700">{row.assigned_customers}</td>
              <td className="px-4 py-3 text-right text-gray-700">
                {formatCurrency(row.revenue)}
              </td>
              <td className="px-4 py-3 text-right text-gray-700">
                {formatRating(row.rating)}
              </td>
              <td className="px-4 py-3 text-right text-gray-700">
                {row.sessions_completed}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
