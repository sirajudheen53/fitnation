/**
 * Dashboard type definitions — FBOS-008.
 */

export interface DashboardOverview {
  total_members: number;
  active_memberships: number;
  mrr: string;
  today_attendance: number;
  trainer_count: number;
  pending_payments: number;
}

export interface RevenueDataPoint {
  label: string;
  amount: number;
}

export interface RevenueResponse {
  daily: RevenueDataPoint[];
  weekly: RevenueDataPoint[];
  monthly: RevenueDataPoint[];
}

export interface AttendanceTrendPoint {
  hour: string;
  check_ins: number;
}

export interface AttendanceDashboardData {
  peak_hours: AttendanceTrendPoint[];
  weekly_trend: AttendanceTrendPoint[];
}

export interface MembershipBreakdown {
  active: number;
  expired: number;
  cancelled: number;
}

export interface PlanDistribution {
  plan: string;
  count: number;
}

export interface MembershipStatsData {
  breakdown: MembershipBreakdown;
  plan_distribution: PlanDistribution[];
}

export interface TrainerOverviewData {
  id: number;
  name: string;
  revenue: number;
  rating: number;
  active_clients: number;
}

export interface PendingPayment {
  id: number;
  customer_name: string;
  amount: number;
  due_date: string | null;
}
