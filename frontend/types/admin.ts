/**
 * Platform admin type definitions — Sprint 10 (issues #39–#45).
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

/** Statuses the admin can move a gym between via PATCH (issue #43). */
export type AdminTenantSwitchStatus = "active" | "suspended";

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

// ── Subscription plan admin CRUD (issue #44) ────────────────────

/**
 * A platform subscription plan row (GET /api/v1/admin/plans/).
 * This is the tier gyms pay FitNation for — not a gym-level membership plan.
 */
export interface AdminSubscriptionPlan {
  id: number;
  /** Catalog key — the model restricts codes to starter/professional/enterprise. */
  code: string;
  name: string;
  /** Decimal strings as returned by DRF ("999.00"). */
  price_monthly: string;
  price_yearly: string;
  max_branches: number;
  max_customers: number;
  max_trainers: number;
  features: Record<string, unknown>;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

/** Body for POST/PATCH /api/v1/admin/plans/{id}/. */
export interface AdminPlanFormData {
  code: string;
  name: string;
  price_monthly: string;
  price_yearly: string;
  max_branches: number;
  max_customers: number;
  max_trainers: number;
  features: Record<string, unknown>;
  is_active: boolean;
  sort_order: number;
}

// ── Support impersonation (issue #45) ───────────────────────────

/** Result of POST /api/v1/admin/tenants/{id}/impersonate/. */
export interface ImpersonateTenantResult {
  token: string;
  /** ISO timestamp — the backend enforces the 30-minute lifetime. */
  expires_at: string;
  owner_email: string;
}

// ── Gym edit & lifecycle (admin platform gap fix) ───────────────

/**
 * Body for PATCH /api/v1/admin/tenants/{id}/ — all fields optional.
 *
 * `status` only accepts "active"/"suspended" (suspend/reactivate);
 * archiving a gym happens via DELETE, never via PATCH.
 */
export interface AdminTenantUpdateFormData {
  name?: string;
  contact_email?: string;
  contact_phone?: string;
  subscription_plan?: SubscriptionPlanCode | string;
  status?: "active" | "suspended";
}

/** Result of POST /api/v1/admin/tenants/{id}/rotate-credentials/. */
export interface AdminRotateCredentialsResult {
  owner_email: string;
  /** Generated once — shown to the admin exactly once for handover. */
  owner_password: string;
}