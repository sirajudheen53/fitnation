"use client";

import { Users, CreditCard, UserCheck, CalendarCheck } from "lucide-react";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { Branch, BranchStats } from "@/types/branch";
import { formatBranchAddress, formatBranchTime, getBranchStatus } from "./BranchTable";

/** Render an empty-state fallback for stats when the backend has no stats endpoint. */
export function emptyBranchStats(): BranchStats {
  return {
    total_customers: 0,
    active_memberships: 0,
    assigned_trainers: 0,
    todays_attendance: 0,
  };
}

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
}

export function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
          {icon}
        </div>
        <div>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  );
}

interface BranchInfoProps {
  branch: Branch;
}

export function BranchInfo({ branch }: BranchInfoProps) {
  const status = getBranchStatus(branch);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold text-gray-900">{branch.name}</h2>
        <Badge variant={status.variant}>{status.label}</Badge>
        {branch.is_headquarters && <Badge variant="info">Headquarters</Badge>}
        <Badge variant="default">{branch.branch_type === "main" ? "Main" : "Sub-branch"}</Badge>
      </div>

      <dl className="space-y-3 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-gray-500">Address</dt>
          <dd className="text-right text-gray-900">
            {branch.address_line1}
            {branch.address_line2 ? `, ${branch.address_line2}` : ""}
            <br />
            {formatBranchAddress(branch)}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-gray-500">Phone</dt>
          <dd className="text-gray-900">{branch.phone || "—"}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-gray-500">Email</dt>
          <dd className="text-gray-900">{branch.email || "—"}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-gray-500">Hours</dt>
          <dd className="text-gray-900">
            {formatBranchTime(branch.opening_time)} – {formatBranchTime(branch.closing_time)}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-gray-500">Operating days</dt>
          <dd className="text-gray-900">
            {branch.operating_days.length ? branch.operating_days.join(", ") : "—"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

interface BranchStatsGridProps {
  stats: BranchStats;
  className?: string;
}

export function BranchStatsGrid({ stats, className }: BranchStatsGridProps) {
  return (
    <div className={cn("grid grid-cols-2 gap-4 lg:grid-cols-4", className)}>
      <StatCard label="Total customers" value={stats.total_customers} icon={<Users className="h-5 w-5" />} />
      <StatCard label="Active memberships" value={stats.active_memberships} icon={<CreditCard className="h-5 w-5" />} />
      <StatCard label="Assigned trainers" value={stats.assigned_trainers} icon={<UserCheck className="h-5 w-5" />} />
      <StatCard label="Today's attendance" value={stats.todays_attendance} icon={<CalendarCheck className="h-5 w-5" />} />
    </div>
  );
}
