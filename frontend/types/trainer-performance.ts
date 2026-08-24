/**
 * Trainer performance type definitions — FBOS-024.
 */

/** Monthly performance snapshot from the trainer-performance endpoint. */
export interface TrainerPerformanceRecord {
  id: number;
  trainer: number;
  trainer_email: string;
  month: string; // YYYY-MM
  revenue: string;
  customer_count: number;
  rating_avg: string | null;
  sessions_completed: number;
  created_at: string;
  updated_at: string;
}

export type TrainerPerformanceListResponse = TrainerPerformanceRecord[];

/** Aggregated performance + monthly series from /trainers/{id}/performance/. */
export interface TrainerPerformanceDetail {
  trainer_id: number;
  total_revenue: number;
  total_sessions_completed: number;
  average_rating: number | null;
  average_customer_count: number;
  latest_month: string | null;
  monthly_records: TrainerPerformanceRecord[];
}

/** Metrics from /trainers/{id}/metrics/ (users app). */
export interface TrainerMetrics {
  trainer_id: number;
  active_clients: number;
  rating: number;
  max_clients: number;
  utilization: number;
  total_assignments: number;
}

/** Joined row combining a trainer profile with its latest performance snapshot. */
export interface TrainerPerformanceRow {
  trainer_id: number;
  name: string;
  specialization: string | null;
  rating: number | null;
  assigned_customers: number;
  active_plans: number;
  attendance_rate: number | null;
  revenue: number;
  sessions_completed: number;
}
