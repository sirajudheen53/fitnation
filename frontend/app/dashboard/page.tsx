"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Users,
  CreditCard,
  Wallet,
  CalendarCheck,
  Dumbbell,
  AlertCircle,
} from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { MetricCard } from "@/features/dashboard/components/MetricCard";
import { RevenueChart } from "@/features/dashboard/components/RevenueChart";
import { AttendanceChart } from "@/features/dashboard/components/AttendanceChart";
import { MembershipStats } from "@/features/dashboard/components/MembershipStats";
import { TrainerOverview } from "@/features/dashboard/components/TrainerOverview";
import { PendingPayments } from "@/features/dashboard/components/PendingPayments";
import { Alert } from "@/components/ui";
import {
  fetchDashboardOverview,
  fetchDashboardRevenue,
  fetchDashboardAttendance,
  fetchDashboardMemberships,
  fetchDashboardTrainers,
  fetchDashboardPendingPayments,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type {
  DashboardOverview,
  RevenueResponse,
  AttendanceDashboardData,
  MembershipStatsData,
  TrainerOverviewData,
  PendingPayment,
} from "@/types/dashboard";

export default function DashboardPage() {
  const router = useRouter();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [revenue, setRevenue] = useState<RevenueResponse | null>(null);
  const [attendance, setAttendance] = useState<AttendanceDashboardData | null>(null);
  const [memberships, setMemberships] = useState<MembershipStatsData | null>(null);
  const [trainers, setTrainers] = useState<TrainerOverviewData[]>([]);
  const [payments, setPayments] = useState<PendingPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/dashboard")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/dashboard");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [ov, rev, att, mem, trn, pay] = await Promise.all([
          fetchDashboardOverview(authToken),
          fetchDashboardRevenue(authToken),
          fetchDashboardAttendance(authToken),
          fetchDashboardMemberships(authToken),
          fetchDashboardTrainers(authToken),
          fetchDashboardPendingPayments(authToken),
        ]);
        setOverview(ov);
        setRevenue(rev);
        setAttendance(att);
        setMemberships(mem);
        setTrainers(trn);
        setPayments(pay);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const metrics = [
    {
      title: "Total members",
      value: overview?.total_members ?? 0,
      icon: Users,
      accent: "text-brand-600",
    },
    {
      title: "Active memberships",
      value: overview?.active_memberships ?? 0,
      icon: CreditCard,
      accent: "text-green-600",
    },
    {
      title: "MRR",
      value: overview ? `₹${Number(overview.mrr || 0).toLocaleString()}` : "₹0",
      icon: Wallet,
      accent: "text-indigo-600",
    },
    {
      title: "Today's attendance",
      value: overview?.today_attendance ?? 0,
      icon: CalendarCheck,
      accent: "text-amber-600",
    },
    {
      title: "Trainers",
      value: overview?.trainer_count ?? 0,
      icon: Dumbbell,
      accent: "text-purple-600",
    },
    {
      title: "Pending payments",
      value: overview?.pending_payments ?? 0,
      icon: AlertCircle,
      accent: "text-red-600",
    },
  ];

  return (
    <DashboardLayout title="Dashboard">
      {error && <Alert variant="error">{error}</Alert>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {metrics.map((m) => (
          <MetricCard
            key={m.title}
            title={m.title}
            value={m.value}
            icon={m.icon}
            accent={m.accent}
          />
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RevenueChart data={revenue ?? { daily: [], weekly: [], monthly: [] }} loading={loading} />
        <AttendanceChart
          data={attendance ?? { peak_hours: [], weekly_trend: [] }}
          loading={loading}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <MembershipStats
          data={memberships ?? { breakdown: { active: 0, expired: 0, cancelled: 0 }, plan_distribution: [] }}
          loading={loading}
        />
        <TrainerOverview trainers={trainers} loading={loading} />
      </div>

      <div className="mt-6">
        <PendingPayments payments={payments} loading={loading} />
      </div>
    </DashboardLayout>
  );
}
