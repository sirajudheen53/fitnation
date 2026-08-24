/**
 * Branch type definitions — FBOS-023.
 */

export interface Branch {
  id: number;
  uuid: string;
  name: string;
  branch_type: "main" | "sub";
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  latitude: string | null;
  longitude: string | null;
  phone: string;
  email: string;
  opening_time: string;
  closing_time: string;
  operating_days: string[];
  is_active: boolean;
  is_headquarters: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BranchFormData {
  name: string;
  branch_type: "main" | "sub";
  address_line1: string;
  address_line2?: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
  email: string;
  opening_time: string;
  closing_time: string;
  operating_days: string[];
  is_active: boolean;
  is_headquarters: boolean;
}

/** Derived stats shown on the branch detail page. */
export interface BranchStats {
  total_customers: number;
  active_memberships: number;
  assigned_trainers: number;
  todays_attendance: number;
}

export type BranchListResponse = Branch[];
