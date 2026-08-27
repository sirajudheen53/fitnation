"use client";

import Link from "next/link";
import {
  CalendarDays,
  User,
  Activity,
  CheckCircle2,
  Hash,
  Flame,
  Clock,
  CreditCard,
  Target,
  Ruler,
  HeartPulse,
} from "lucide-react";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui";
import type { Customer } from "@/types/customer";
import type { ProgressSummary } from "@/types/customer-detail";

/** Format a member-since date (YYYY-MM-DD or ISO) to a readable date. */
export function formatMemberSince(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Build a numeric stat from a string/number/null value. */
export function toNumber(value: string | number | null | undefined): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

interface OverviewTabProps {
  customer: Customer;
  summary?: ProgressSummary | null;
}

export function OverviewTab({ customer, summary }: OverviewTabProps) {
  const profile = summary?.health_profile ?? null;
  const activeGoals = summary?.fitness_goals?.filter((g) => g.status === "active").length ?? 0;

  const stats: { label: string; value: string; icon: React.ReactNode }[] = [
    {
      label: "Member since",
      value: formatMemberSince(customer.created_at),
      icon: <CalendarDays className="h-5 w-5" />,
    },
    {
      label: "BMI",
      value: profile?.bmi != null ? String(Number(profile.bmi).toFixed(1)) : "—",
      icon: <Activity className="h-5 w-5" />,
    },
    {
      label: "Weight (kg)",
      value: profile?.weight_kg != null ? String(Number(profile.weight_kg).toFixed(1)) : "—",
      icon: <Hash className="h-5 w-5" />,
    },
    {
      label: "Progress photos",
      value: summary ? String(summary.progress_photo_count) : "—",
      icon: <CheckCircle2 className="h-5 w-5" />,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Primary stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                {s.icon}
              </div>
              <div>
                <p className="text-lg font-semibold text-gray-900">{s.value}</p>
                <p className="text-xs text-gray-500">{s.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick summary cards */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900">Quick summary</h3>
        </CardHeader>
        <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Membership status</p>
            {customer.is_active ? (
              <Badge variant="success">Active</Badge>
            ) : (
              <Badge variant="danger">Inactive</Badge>
            )}
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Contact</p>
            <p className="text-sm text-gray-700">{customer.email}</p>
            <p className="text-sm text-gray-500">{customer.phone || "No phone on file"}</p>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Emergency contact</p>
            <p className="text-sm text-gray-700">
              {customer.emergency_contact_name || "—"}
            </p>
            <p className="text-sm text-gray-500">{customer.emergency_contact_phone || "—"}</p>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Gender</p>
            <p className="text-sm capitalize text-gray-700">{customer.gender || "—"}</p>
          </div>
        </CardBody>
      </Card>

      {/* Tab links */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Link
          href={`/customers/${customer.id}#goals`}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Target className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium text-gray-900">Fitness Goals</p>
            <p className="text-xs text-gray-500">
              {activeGoals > 0 ? `${activeGoals} active goal${activeGoals > 1 ? "s" : ""}` : "No goals yet"}
            </p>
          </div>
        </Link>

        <Link
          href={`/customers/${customer.id}#measurements`}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Ruler className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium text-gray-900">Body Measurements</p>
            <p className="text-xs text-gray-500">
              {summary?.latest_measurement
                ? `Last: ${formatMemberSince(summary.latest_measurement.date_logged)}`
                : "No measurements yet"}
            </p>
          </div>
        </Link>

        <Link
          href={`/customers/${customer.id}#health`}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <HeartPulse className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium text-gray-900">Health Profile</p>
            <p className="text-xs text-gray-500">
              {profile ? "On file" : "Not yet added"}
            </p>
          </div>
        </Link>
      </div>

      {/* Attendance */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900">Attendance</h3>
        </CardHeader>
        <CardBody>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <User className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-gray-600">
                  Full attendance history and check-in streak are available from the Attendance
                  section.
                </p>
              </div>
            </div>
            <Link href={`/attendance?customer=${encodeURIComponent(customer.email)}`}>
              <Badge variant="info" className="cursor-pointer hover:bg-blue-100">
                View attendance →
              </Badge>
            </Link>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
