"use client";

import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PerformanceMetricCardProps {
  label: string;
  value: string;
  icon: ReactNode;
  hint?: string;
}

export function PerformanceMetricCard({
  label,
  value,
  icon,
  hint,
}: PerformanceMetricCardProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
          {hint && <p className="mt-0.5 text-xs text-gray-400">{hint}</p>}
        </div>
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600")}>
          {icon}
        </div>
      </div>
    </div>
  );
}
