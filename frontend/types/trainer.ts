/**
 * Trainer type definitions — FBOS-007.
 */

export interface Trainer {
  id: number;
  user_id: number | null;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  specialization: string | null;
  bio: string | null;
  certifications: string[];
  experience_years: number | null;
  branch_id: number | null;
  is_active: boolean;
  rating: string;
  revenue: string;
  active_clients: number;
  created_at: string;
  updated_at: string;
}

export interface TrainerFormData {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  specialization?: string;
  bio?: string;
  certifications: string[];
  experience_years?: number;
  branch_id?: number;
  is_active: boolean;
}

export interface TrainerAssignment {
  id: number;
  trainer_id: number;
  trainer_name: string;
  customer_id: number;
  customer_name: string;
  branch_id: number | null;
  assigned_at: string;
}

export interface AssignmentFormData {
  trainer_id: number;
  customer_id: number;
  branch_id?: number;
}

export interface ScheduleSlot {
  id: number;
  trainer_id: number;
  trainer_name: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  title: string;
}

export interface TrainerListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Trainer[];
}

export interface AssignmentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: TrainerAssignment[];
}

export interface ScheduleListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScheduleSlot[];
}
