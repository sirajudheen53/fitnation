/**
 * Platform admin type definitions — Sprint 10 (issues #39, #41, #42).
 *
 * Field sets mirror the backend `apps/admin_ops` serializers exactly:
 * tenants are cross-tenant rows with computed member/branch counts.
 */

// ── Subscription plans (platform tiers gyms pay FitNation) ──────

export const SUBSCRIPTION_PLANS = [
  { code: "starter", label: "Starter" },
  { code: "professional", label: "Professional" },
  { code: "enterprise", label: "Enterprise" },
] as const;

export type SubscriptionPlanCode = (typeof SUBSCRIPTION_PLANS)[number]["code"];

// ── Tenant (gym) as seen by the platform admin ──────────────────

/** A gym (tenant) in the admin gyms list (GET /api/v1/admin/tenants/). */
export interface AdminTenant {
  id: number;
  name: string;
  subscription_plan: string;
  status: string;
  contact_email: string;
  contact_phone: string;
  member_count: number;
  branch_count: number;
  created_at: string;
}

// ── Admin-driven gym onboarding ─────────────────────────────────

/** Body for POST /api/v1/admin/tenants/onboard/ (issue #40). */
export interface AdminOnboardGymFormData {
  gym_name: string;
  contact_name: string;
  owner_email: string;
  owner_phone: string;
  branch_name: string;
  plan_code: SubscriptionPlanCode | string;
}

/** Result of a successful admin onboarding (issue #40). */
export interface AdminOnboardGymResult {
  tenant_id: number;
  tenant_name: string;
  owner_email: string;
  /** Generated once — shown to the admin exactly once for handover. */
  owner_password: string;
  branch_name: string;
  plan_code: string;
}