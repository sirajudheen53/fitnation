/**
 * Attendance type definitions — FBOS-006.
 */

export type AttendanceStatus = "present" | "late" | "absent" | "left";

export type AttendanceType = "customer" | "trainer" | "staff";

export interface AttendanceRecord {
  id: number;
  person_id: number;
  person_name: string;
  person_type: AttendanceType;
  branch_id: number | null;
  branch_name: string | null;
  check_in_time: string | null;
  check_out_time: string | null;
  status: AttendanceStatus;
  date: string;
  created_at: string;
  updated_at: string;
}

export interface CheckInData {
  person_id: number;
  person_type: AttendanceType;
  branch_id?: number;
  status?: AttendanceStatus;
}

export interface AttendanceStats {
  today_count: number;
  peak_hour: string | null;
  peak_hour_count: number;
  weekly_check_ins: number;
  avg_daily_check_ins: number;
  most_frequent_dropout_hour: string | null;
}

export interface AttendanceSummary {
  labels: string[];
  check_ins: number[];
}

export interface AttendanceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: AttendanceRecord[];
}

export interface AttendanceStatsResponse {
  stats: AttendanceStats;
  summary: AttendanceSummary;
}
