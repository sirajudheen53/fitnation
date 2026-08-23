/**
 * Membership type definitions — FBOS-004.
 */

export type MembershipPlanType = "monthly" | "quarterly" | "half_yearly" | "yearly";

export type MembershipStatus = "active" | "expired" | "cancelled" | "pending";

export interface MembershipPlan {
  id: number;
  name: string;
  price: string;
  duration_days: number;
  plan_type: MembershipPlanType;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MembershipPlanFormData {
  name: string;
  price: number;
  duration_days: number;
  plan_type: MembershipPlanType;
  description?: string;
  is_active: boolean;
}

export interface Membership {
  id: number;
  customer_id: number;
  customer_name: string;
  plan_id: number;
  plan_name: string;
  start_date: string;
  end_date: string;
  status: MembershipStatus;
  price: number;
  created_at: string;
  updated_at: string;
}

export interface AssignMembershipData {
  customer_id: number;
  plan_id: number;
  start_date: string;
  end_date: string;
  coupon_code?: string;
  amount_paid?: number;
}

export interface Coupon {
  id: number;
  code: string;
  description: string | null;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  valid_from: string;
  valid_until: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CouponFormData {
  code: string;
  description?: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  valid_from: string;
  valid_until?: string;
  is_active: boolean;
}

export interface MembershipListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Membership[];
}

export interface MembershipPlanListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: MembershipPlan[];
}

export interface CouponListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Coupon[];
}
