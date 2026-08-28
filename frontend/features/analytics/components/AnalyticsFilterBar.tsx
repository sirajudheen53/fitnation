"use client";

import { Download } from "lucide-react";
import { Button, Input } from "@/components/ui";
import type { Branch } from "@/types/branch";
import type { DateRangePreset } from "@/types/analytics";

interface AnalyticsFilterBarProps {
  preset: DateRangePreset;
  dateFrom: string;
  dateTo: string;
  branch: string;
  branches: Branch[];
  onPresetChange: (preset: DateRangePreset) => void;
  onDateFromChange: (date: string) => void;
  onDateToChange: (date: string) => void;
  onBranchChange: (branch: string) => void;
  onExport: () => void;
  exporting?: boolean;
}

const PRESETS: { value: DateRangePreset; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "Last 7 days" },
  { value: "month", label: "Last 30 days" },
  { value: "custom", label: "Custom" },
];

/** Date-range + branch filter bar with CSV export (FBOS-030). */
export function AnalyticsFilterBar({
  preset,
  dateFrom,
  dateTo,
  branch,
  branches,
  onPresetChange,
  onDateFromChange,
  onDateToChange,
  onBranchChange,
  onExport,
  exporting = false,
}: AnalyticsFilterBarProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm lg:flex-row lg:items-end lg:justify-between">
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
        {/* Date range presets */}
        <div className="space-y-1.5">
          <span className="block text-sm font-medium text-gray-700">Date range</span>
          <div className="flex flex-wrap gap-1 rounded-lg bg-gray-100 p-1">
            {PRESETS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => onPresetChange(p.value)}
                aria-pressed={preset === p.value}
                className={
                  preset === p.value
                    ? "rounded-md bg-white px-3 py-1.5 text-sm font-medium text-brand-700 shadow-sm"
                    : "rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900"
                }
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom date inputs */}
        {preset === "custom" && (
          <div className="flex flex-wrap items-end gap-3">
            <Input
              type="date"
              label="From"
              value={dateFrom}
              onChange={(e) => onDateFromChange(e.target.value)}
            />
            <Input
              type="date"
              label="To"
              value={dateTo}
              onChange={(e) => onDateToChange(e.target.value)}
            />
          </div>
        )}

        {/* Branch filter */}
        <div className="space-y-1.5">
          <label
            htmlFor="analytics-branch"
            className="block text-sm font-medium text-gray-700"
          >
            Branch
          </label>
          <select
            id="analytics-branch"
            value={branch}
            onChange={(e) => onBranchChange(e.target.value)}
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">All branches</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Button
        variant="outline"
        onClick={onExport}
        loading={exporting}
        aria-label="Export to CSV"
      >
        <Download className="h-4 w-4" />
        Export CSV
      </Button>
    </div>
  );
}
