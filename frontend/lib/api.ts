/**
 * API client for FBOS backend.
 * All API calls go through this module — components should never use raw fetch.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: Record<string, unknown>,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Extract a human-readable error message from an unknown caught value. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return (err.data?.error as string | undefined) || err.message;
  }
  if (err instanceof Error) {
    // fetch() rejects with a bare TypeError on network/CORS failures — the
    // browser gives no status or body (e.g. a preflight-blocked request, so
    // the server never even saw it). Translate to something actionable.
    if (err instanceof TypeError && /fetch|network/i.test(err.message)) {
      return "Could not reach the server — check your connection and try again.";
    }
    return err.message;
  }
  if (typeof err === "string") return err;
  return "An unexpected error occurred.";
}

/**
 * Normalise a backend list response into a plain array.
 *
 * Some DRF endpoints return a plain array while others wrap items in a
 * paginated envelope (`{count, next, previous, results}` or `{results, total}`).
 * The UI expects arrays everywhere, so list fetchers funnel their raw response
 * through this helper. It tolerates both shapes - and returns `[]` for
 * anything else - so a contract drift can never crash a render.
 */
export function unwrapList<T>(
  res: T[] | { results?: T[] } | Record<string, unknown> | null | undefined,
): T[] {
  if (Array.isArray(res)) return res;
  if (
    res &&
    typeof res === "object" &&
    Array.isArray((res as { results?: unknown }).results)
  ) {
    return (res as { results: T[] }).results;
  }
  return [];
}

/**
 * Resolve a backend media URL for display.
 *
 * Django serves media at a relative path (`/media/...`), which only works
 * when the page is served from the API origin. Prefix the API origin so
 * images render from the frontend domain; absolute URLs pass through.
 */
export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  try {
    const origin = new URL(API_BASE_URL).origin;
    return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
  } catch {
    return path;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string;
  headers?: Record<string, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, headers = {} } = options;

  // Multipart uploads (e.g. customer profile photo) must NOT set
  // Content-Type - the browser supplies it with the form boundary.
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  const config: RequestInit = {
    method,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
  };

  if (token) {
    config.headers = { ...config.headers, Authorization: `Token ${token}` };
  }

  if (body !== undefined) {
    config.body = isFormData ? (body as FormData) : JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, config);
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;

  if (!res.ok) {
    const message =
      (data.error as string) ||
      (data.detail as string) ||
      `Request failed with status ${res.status}`;
    throw new ApiError(res.status, data, message);
  }

  return data as T;
}

/* ── Auth endpoints ────────────────────────────────────────────── */

export interface SignupRequest {
  business_name: string;
  contact_name: string;
  email: string;
  phone: string;
  password: string;
}

export interface SignupResponse {
  registration_id: number;
  message: string;
  next_step: string;
}

export function signup(data: SignupRequest): Promise<SignupResponse> {
  return request<SignupResponse>("/auth/signup/", {
    method: "POST",
    body: data,
  });
}

/* ── Email verification ────────────────────────────────────────── */

export interface VerifyEmailResponse {
  message: string;
  registration_id: number;
  next_step: string;
}

export function verifyEmail(token: string): Promise<VerifyEmailResponse> {
  return request<VerifyEmailResponse>(`/auth/verify-email/?token=${token}`);
}

/* ── Resend verification ──────────────────────────────────────── */

export function resendVerification(email: string): Promise<{ message: string }> {
  return request<{ message: string }>("/auth/resend-verification/", {
    method: "POST",
    body: { email },
  });
}

/* ── Subscription plans ───────────────────────────────────────── */

export interface PlanFeatures {
  whatsapp: boolean;
  ai_coach: boolean;
  custom_branding: boolean;
  [key: string]: boolean;
}

export interface SubscriptionPlan {
  code: string;
  name: string;
  price_monthly: string;
  price_yearly: string;
  max_branches: number;
  max_customers: number;
  max_trainers: number;
  features: PlanFeatures;
}

export interface PlansResponse {
  plans: SubscriptionPlan[];
}

export function getPlans(): Promise<PlansResponse> {
  return request<PlansResponse>("/subscriptions/plans/");
}

/* ── Select plan ───────────────────────────────────────────────── */

export interface SelectPlanRequest {
  registration_id: number;
  plan_code: string;
}

export interface SelectPlanResponse {
  message: string;
  tenant: {
    id: number;
    uuid: string;
    name: string;
    subscription_plan: string;
  };
  auth_token: string;
  next_step: string;
}

export function selectPlan(data: SelectPlanRequest): Promise<SelectPlanResponse> {
  return request<SelectPlanResponse>("/auth/select-plan/", {
    method: "POST",
    body: data,
  });
}

/* ── Onboarding ───────────────────────────────────────────────── */

export interface OnboardingRequest {
  business_type: string;
  branches_count: number;
  primary_branch_name: string;
  primary_branch_address: string;
  primary_branch_phone: string;
}

export interface OnboardingResponse {
  message: string;
  redirect_to: string;
}

export function completeOnboarding(
  data: OnboardingRequest,
  token: string,
): Promise<OnboardingResponse> {
  return request<OnboardingResponse>("/auth/onboarding/", {
    method: "PUT",
    body: data,
    token,
  });
}

/* ── Login ────────────────────────────────────────────────────── */

export interface LoginRequest {
  email: string;
  password: string;
  device_type?: string;
}

export interface LoginUser {
  id: number;
  email: string;
  name: string;
  role: string;
  tenant_id: number | null;
  tenant_name: string | null;
  is_owner: boolean;
}

export interface LoginResponse {
  token: string;
  user: LoginUser;
  permissions: string[];
}

import {
  Customer,
  CustomerFormData,
  CustomerListResponse,
  HealthProfileFormData,
} from "@/types/customer";

export function fetchCustomers(token: string): Promise<CustomerListResponse> {
  return request<CustomerListResponse>("/customers/customers/", { token });
}

export function fetchCustomer(id: number | string, token: string): Promise<Customer> {
  return request<Customer>(`/customers/customers/${id}/`, { token });
}

/**
 * Build the request body for a customer create/update.
 *
 * With a photo File the body becomes multipart FormData (the browser sets
 * the boundary); otherwise it stays JSON. `profile_photo: null` is kept in
 * the JSON body so the backend can clear an existing photo on update.
 */
export function buildCustomerBody(
  data: CustomerFormData,
): FormData | Record<string, unknown> {
  // The backend contract names the branch field `branch` (ADR-001: no
  // aliases) while the form state uses `branch_id` - translate here.
  // `admission_fee` is form-only state for the create flow (it becomes a
  // separate Payment row) and must never reach the customer endpoint.
  const { profile_photo, branch_id, admission_fee, ...fields } = data;

  if (typeof File !== "undefined" && profile_photo instanceof File) {
    const form = new FormData();
    for (const [key, value] of Object.entries(fields)) {
      if (value !== undefined) form.append(key, String(value));
    }
    if (branch_id !== undefined) form.append("branch", String(branch_id));
    form.append("profile_photo", profile_photo);
    return form;
  }

  const body: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined) body[key] = value;
  }
  if (branch_id !== undefined) body.branch = branch_id;
  if (profile_photo === null) body.profile_photo = null;
  return body;
}

export function createCustomer(
  data: CustomerFormData,
  token: string,
): Promise<Customer> {
  return request<Customer>("/customers/customers/", {
    method: "POST",
    body: buildCustomerBody(data),
    token,
  });
}

export function updateCustomer(
  id: number | string,
  data: CustomerFormData,
  token: string,
): Promise<Customer> {
  return request<Customer>(`/customers/customers/${id}/`, {
    method: "PATCH",
    body: buildCustomerBody(data),
    token,
  });
}

export function updateHealthProfile(
  id: number | string,
  data: HealthProfileFormData,
  token: string,
): Promise<Customer> {
  return request<Customer>(`/customers/customers/${id}/health-profile/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

export function deleteCustomer(id: number | string, token: string): Promise<void> {
  return request<void>(`/customers/customers/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* ── Memberships ──────────────────────────────────────────────── */

import {
  AssignMembershipData,
  Coupon,
  CouponFormData,
  CouponListResponse,
  Membership,
  MembershipListResponse,
  MembershipPlan,
  MembershipPlanFormData,
  MembershipPlanListResponse,
} from "@/types/membership";

/* Membership plans */

export function fetchMembershipPlans(token: string): Promise<MembershipPlanListResponse> {
  return request<MembershipPlanListResponse>("/memberships/membership-plans/", { token });
}

export function fetchMembershipPlan(
  id: number | string,
  token: string,
): Promise<MembershipPlan> {
  return request<MembershipPlan>(`/memberships/membership-plans/${id}/`, { token });
}

export function createMembershipPlan(
  data: MembershipPlanFormData,
  token: string,
): Promise<MembershipPlan> {
  return request<MembershipPlan>("/memberships/membership-plans/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateMembershipPlan(
  id: number | string,
  data: MembershipPlanFormData,
  token: string,
): Promise<MembershipPlan> {
  return request<MembershipPlan>(`/memberships/membership-plans/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteMembershipPlan(id: number | string, token: string): Promise<void> {
  return request<void>(`/memberships/membership-plans/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* Active memberships */

export function fetchMemberships(token: string): Promise<MembershipListResponse> {
  return request<MembershipListResponse>("/memberships/memberships/", { token });
}

/**
 * Map the form-shaped assign payload onto the backend contract. The DRF
 * MembershipSerializer only accepts `customer` + `plan` primary keys —
 * `customer_id` is a read-only output field, so posting the form shape
 * as-is gets silently dropped and 400s with "This field is required."
 */
export function buildMembershipBody(
  data: AssignMembershipData,
): Record<string, unknown> {
  return {
    customer: data.customer_id,
    plan: data.plan_id,
    start_date: data.start_date,
    end_date: data.end_date,
  };
}

export function assignMembership(
  data: AssignMembershipData,
  token: string,
): Promise<Membership> {
  return request<Membership>("/memberships/memberships/", {
    method: "POST",
    body: buildMembershipBody(data),
    token,
  });
}

export function cancelMembership(id: number | string, token: string): Promise<Membership> {
  return request<Membership>(`/memberships/memberships/${id}/cancel/`, {
    method: "POST",
    token,
  });
}

/**
 * Renew a membership: extends end_date by `days` (omitted → the backend
 * defaults to plan.duration_days, else 30), sets status back to ACTIVE and
 * re-syncs door access. Returns the updated membership.
 */
export function renewMembership(
  id: number | string,
  token: string,
  days?: number,
): Promise<Membership> {
  return request<Membership>(`/memberships/memberships/${id}/renewal/`, {
    method: "POST",
    body: days !== undefined ? { days } : undefined,
    token,
  });
}

/* Coupons */

export function fetchCoupons(token: string): Promise<CouponListResponse> {
  return request<CouponListResponse>("/memberships/coupons/", { token });
}

export function createCoupon(data: CouponFormData, token: string): Promise<Coupon> {
  return request<Coupon>("/memberships/coupons/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateCoupon(
  id: number | string,
  data: CouponFormData,
  token: string,
): Promise<Coupon> {
  return request<Coupon>(`/memberships/coupons/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteCoupon(id: number | string, token: string): Promise<void> {
  return request<void>(`/memberships/coupons/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* ── Payments ────────────────────────────────────────────────── */

import {
  Invoice,
  InvoiceListResponse,
  Payment,
  PaymentFormData,
  PaymentKind,
  PaymentListResponse,
  PaymentStatus,
  RevenueSummary,
} from "@/types/payment";

/**
 * List payments with the backend's optional queryset filters
 * (e.g. { customer: id, kind: "admission" } → ?customer=1&kind=admission).
 */
export function fetchPayments(
  token: string,
  params?: { customer?: number | string; kind?: PaymentKind; status?: PaymentStatus },
): Promise<PaymentListResponse> {
  const query = new URLSearchParams();
  if (params?.customer !== undefined && params?.customer !== "")
    query.set("customer", String(params.customer));
  if (params?.kind) query.set("kind", params.kind);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return request<PaymentListResponse>(`/payments/${qs ? `?${qs}` : ""}`, { token });
}

export function fetchPayment(id: number | string, token: string): Promise<Payment> {
  return request<Payment>(`/payments/${id}/`, { token });
}

export function createPayment(data: PaymentFormData, token: string): Promise<Payment> {
  return request<Payment>("/payments/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updatePayment(
  id: number | string,
  data: Partial<PaymentFormData>,
  token: string,
): Promise<Payment> {
  return request<Payment>(`/payments/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

export function fetchRevenueSummary(token: string): Promise<RevenueSummary> {
  return request<RevenueSummary>("/payments/revenue-summary/", { token });
}

/* Invoices */

export function fetchInvoices(token: string): Promise<InvoiceListResponse> {
  return request<InvoiceListResponse>("/invoices/", { token });
}

export function fetchInvoice(id: number | string, token: string): Promise<Invoice> {
  return request<Invoice>(`/invoices/${id}/`, { token });
}

/* ── Razorpay payments (FBOS-020) ─────────────────────────────── */

import {
  CreateRazorpayOrderRequest,
  CreateRazorpayOrderResponse,
  RazorpayConfig,
  RazorpayConfigUpdate,
  RazorpayPayment,
  RazorpayPaymentListResponse,
  VerifyRazorpayPaymentRequest,
} from "@/types/razorpay";

/** Create a Razorpay order before launching the checkout. */
export function createRazorpayOrder(
  data: CreateRazorpayOrderRequest,
  token: string,
): Promise<CreateRazorpayOrderResponse> {
  return request<CreateRazorpayOrderResponse>("/payments/razorpay/create-order/", {
    method: "POST",
    body: data,
    token,
  });
}

/** Verify the Razorpay signature after a successful payment. */
export function verifyRazorpayPayment(
  data: VerifyRazorpayPaymentRequest,
  token: string,
): Promise<RazorpayPayment> {
  return request<RazorpayPayment>("/payments/razorpay/verify/", {
    method: "POST",
    body: data,
    token,
  });
}

/** Fetch the public Razorpay config (api key + active flag). */
export function fetchRazorpayConfig(token: string): Promise<RazorpayConfig> {
  return request<RazorpayConfig>("/payments/razorpay/config/", { token });
}

/** Update the tenant Razorpay config (admin/owner only). */
export function updateRazorpayConfig(
  data: RazorpayConfigUpdate,
  token: string,
): Promise<{ is_active: boolean }> {
  return request<{ is_active: boolean }>("/payments/razorpay/config/", {
    method: "PATCH",
    body: data,
    token,
  });
}

/** List Razorpay-backed payment history (paginated). */
export function fetchRazorpayPayments(
  token: string,
  params?: { customer?: string; status?: string },
): Promise<RazorpayPaymentListResponse> {
  const query = new URLSearchParams();
  if (params?.customer) query.set("customer", params.customer);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return request<RazorpayPaymentListResponse>(
    `/payments/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

/* ── Attendance ───────────────────────────────────────────────── */

import {
  AttendanceListResponse,
  AttendanceRecord,
  AttendanceStatsResponse,
  CheckInData,
} from "@/types/attendance";

export function fetchAttendance(token: string): Promise<AttendanceListResponse> {
  return request<AttendanceListResponse>("/attendance/attendance/", { token });
}

/** List one customer's attendance records (backend ?customer= filter). */
export function fetchCustomerAttendance(
  customerId: number | string,
  token: string,
): Promise<AttendanceListResponse> {
  return request<AttendanceListResponse>(
    `/attendance/attendance/?customer=${encodeURIComponent(String(customerId))}`,
    { token },
  );
}

export function fetchTrainerAttendance(token: string): Promise<AttendanceListResponse> {
  return request<AttendanceListResponse>("/attendance/trainer-attendance/", { token });
}

export function fetchStaffAttendance(token: string): Promise<AttendanceListResponse> {
  return request<AttendanceListResponse>("/attendance/staff-attendance/", { token });
}

export function fetchAllAttendance(token: string): Promise<AttendanceRecord[]> {
  return Promise.all([
    fetchAttendance(token),
    fetchTrainerAttendance(token),
    fetchStaffAttendance(token),
  ]).then(([customer, trainer, staff]) =>
    [...customer.results, ...trainer.results, ...staff.results].sort(
      (a, b) =>
        new Date(b.check_in_time ?? 0).getTime() -
        new Date(a.check_in_time ?? 0).getTime(),
    ),
  );
}

export function fetchAttendanceStats(token: string): Promise<AttendanceStatsResponse> {
  return request<AttendanceStatsResponse>("/attendance/stats/", { token });
}

export function checkIn(data: CheckInData, token: string): Promise<AttendanceRecord> {
  return request<AttendanceRecord>("/attendance/check-in/", {
    method: "POST",
    body: data,
    token,
  });
}

export function checkOut(id: number | string, token: string): Promise<AttendanceRecord> {
  return request<AttendanceRecord>(`/attendance/attendance/${id}/check-out/`, {
    method: "POST",
    token,
  });
}

/* ── Trainers ─────────────────────────────────────────────────── */

import {
  BranchAssignmentCreatePayload,
  BranchTrainerAssignment,
  PtRemaining,
  SessionBookingPayload,
  SessionStatus,
  Trainer,
  TrainerCreatePayload,
  TrainerListParams,
  TrainerScheduleSlot,
  TrainerSession,
  TrainerUpdatePayload,
} from "@/types/trainer";

/**
 * List trainers (users app — full management surface).
 * Supports the backend's is_active / specialization / search filters.
 */
export function fetchTrainers(
  token: string,
  params?: TrainerListParams,
): Promise<Trainer[]> {
  const query = new URLSearchParams();
  if (params?.is_active !== undefined) query.set("is_active", String(params.is_active));
  if (params?.specialization) query.set("specialization", params.specialization);
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return request<Trainer[] | { results?: Trainer[] }>(
    `/users/trainers/${qs ? `?${qs}` : ""}`,
    { token },
  ).then(unwrapList);
}

export function fetchTrainer(id: number | string, token: string): Promise<Trainer> {
  return request<Trainer>(`/users/trainers/${id}/`, { token });
}

export function createTrainer(
  data: TrainerCreatePayload,
  token: string,
): Promise<Trainer> {
  return request<Trainer>("/users/trainers/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateTrainer(
  id: number | string,
  data: TrainerUpdatePayload,
  token: string,
): Promise<Trainer> {
  return request<Trainer>(`/users/trainers/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * List branch-scoped trainer↔customer assignments (trainers app).
 * The endpoint has no query filters — filter by trainer/customer client-side.
 */
export function fetchTrainerAssignments(
  token: string,
): Promise<BranchTrainerAssignment[]> {
  return request<BranchTrainerAssignment[] | { results?: BranchTrainerAssignment[] }>(
    "/trainer-assignments/",
    { token },
  ).then(unwrapList);
}

export function createTrainerAssignment(
  data: BranchAssignmentCreatePayload,
  token: string,
): Promise<BranchTrainerAssignment> {
  return request<BranchTrainerAssignment>("/trainer-assignments/", {
    method: "POST",
    body: data,
    token,
  });
}

/** Deactivate a branch-scoped assignment (credit-safe, reversible via re-create). */
export function unassignTrainerAssignment(
  id: number,
  token: string,
): Promise<BranchTrainerAssignment> {
  return request<BranchTrainerAssignment>(`/trainer-assignments/${id}/unassign/`, {
    method: "POST",
    token,
  });
}

/**
 * Customer's derived PT session-pack state. 403s for roles without
 * customers.view_customer — callers hide the badge on failure.
 */
export function fetchPtRemaining(
  customerId: number | string,
  token: string,
): Promise<PtRemaining> {
  return request<PtRemaining>(
    `/customers/customers/${customerId}/pt-remaining/`,
    { token },
  );
}

/* ── PT sessions (issue #55) ──────────────────────────────────── */

/** List PT sessions — trainer/customer/status are server-side filters. */
export function fetchTrainerSessions(
  token: string,
  params?: { trainer?: number; customer?: number; status?: SessionStatus },
): Promise<TrainerSession[]> {
  const query = new URLSearchParams();
  if (params?.trainer !== undefined) query.set("trainer", String(params.trainer));
  if (params?.customer !== undefined) query.set("customer", String(params.customer));
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return request<TrainerSession[] | { results?: TrainerSession[] }>(
    `/trainer-sessions/${qs ? `?${qs}` : ""}`,
    { token },
  ).then(unwrapList);
}

/** Book a session — 409s with a machine-readable reason on conflict. */
export function bookTrainerSession(
  data: SessionBookingPayload,
  token: string,
): Promise<TrainerSession> {
  return request<TrainerSession>("/trainer-sessions/", {
    method: "POST",
    body: data,
    token,
  });
}

function sessionAction(id: number, action: string, token: string): Promise<TrainerSession> {
  return request<TrainerSession>(`/trainer-sessions/${id}/${action}/`, {
    method: "POST",
    token,
  });
}

/** Mark completed — redeems one pack credit. */
export function completeTrainerSession(
  id: number,
  token: string,
): Promise<TrainerSession> {
  return sessionAction(id, "complete", token);
}

/** Mark no-show — redeems one pack credit. */
export function noShowTrainerSession(
  id: number,
  token: string,
): Promise<TrainerSession> {
  return sessionAction(id, "no-show", token);
}

/** Cancel — no redemption; restores a redeemed credit. */
export function cancelTrainerSession(
  id: number,
  token: string,
): Promise<TrainerSession> {
  return sessionAction(id, "cancel", token);
}

/** Weekly availability rows for one trainer, Monday→Sunday ordered. */
export function fetchTrainerSchedule(
  trainerId: number | string,
  token: string,
): Promise<TrainerScheduleSlot[]> {
  return request<TrainerScheduleSlot[] | { results?: TrainerScheduleSlot[] }>(
    `/trainer-schedules/?trainer=${encodeURIComponent(String(trainerId))}`,
    { token },
  ).then(unwrapList);
}

/* ── Dashboard ────────────────────────────────────────────────── */
import {
  RevenueReport,
  AttendanceHeatmap,
  MembershipFunnel,
  TopCustomer,
  AnalyticsFilters,
} from "@/types/analytics";

/** Build a query string for analytics endpoints from filter params. */
function buildAnalyticsQuery(params?: AnalyticsFilters): string {
  if (!params) return "";
  const query = new URLSearchParams();
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  if (params.branch !== undefined && params.branch !== "") {
    query.set("branch", String(params.branch));
  }
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

import {
  AttendanceDashboardData,
  DashboardOverview,
  MembershipStatsData,
  PendingPayment,
  RevenueResponse,
  TrainerOverviewData,
} from "@/types/dashboard";

export function fetchDashboardOverview(token: string): Promise<DashboardOverview> {
  return request<DashboardOverview>("/dashboard/overview/", { token });
}

export function fetchDashboardRevenue(token: string): Promise<RevenueResponse> {
  return request<RevenueResponse>("/dashboard/revenue/", { token });
}

export function fetchDashboardAttendance(token: string): Promise<AttendanceDashboardData> {
  return request<AttendanceDashboardData>("/dashboard/attendance/", { token });
}

export function fetchDashboardMemberships(token: string): Promise<MembershipStatsData> {
  return request<MembershipStatsData>("/dashboard/memberships/", { token });
}

export function fetchDashboardTrainers(
  token: string,
): Promise<TrainerOverviewData[]> {
  return request<TrainerOverviewData[] | { results?: TrainerOverviewData[] }>(
    "/dashboard/trainers/",
    { token },
  ).then(unwrapList);
}

export function fetchRevenueReport(
  token: string,
  params?: AnalyticsFilters,
): Promise<RevenueReport[]> {
  return request<RevenueReport[] | { results?: RevenueReport[] }>(
    `/analytics/revenue/${buildAnalyticsQuery(params)}`,
    { token },
  ).then(unwrapList);
}

export function fetchAttendanceHeatmap(
  token: string,
  params?: AnalyticsFilters,
): Promise<AttendanceHeatmap[]> {
  return request<AttendanceHeatmap[] | { results?: AttendanceHeatmap[] }>(
    `/analytics/attendance/heatmap/${buildAnalyticsQuery(params)}`,
    { token },
  ).then(unwrapList);
}

export function fetchMembershipFunnel(
  token: string,
  params?: AnalyticsFilters,
): Promise<MembershipFunnel[]> {
  return request<MembershipFunnel[] | { results?: MembershipFunnel[] }>(
    `/analytics/memberships/funnel/${buildAnalyticsQuery(params)}`,
    { token },
  ).then(unwrapList);
}

export function fetchTopCustomers(
  token: string,
  params?: AnalyticsFilters,
): Promise<TopCustomer[]> {
  return request<TopCustomer[] | { results?: TopCustomer[] }>(
    `/analytics/top-customers/${buildAnalyticsQuery(params)}`,
    { token },
  ).then(unwrapList);
}

export function fetchDashboardPendingPayments(
  token: string,
): Promise<PendingPayment[]> {
  return request<PendingPayment[]>("/dashboard/pending-payments/", { token });
}

export function login(data: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>("/users/auth/login/", {
    method: "POST",
    body: data,
  });
}

/* ── Diet plans & food items ─────────────────────────────────── */

import {
  DietAssignment,
  DietAssignmentFormData,
  DietAssignmentListResponse,
  DietPlan,
  DietPlanFormData,
  DietPlanListResponse,
  FoodItem,
  FoodItemFormData,
  FoodItemListResponse,
  NutritionBreakdown,
} from "@/types/diet";

/* Food items */

export function fetchFoodItems(
  token: string,
  params?: { search?: string; food_group?: string; is_veg?: string },
): Promise<FoodItemListResponse> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.food_group) query.set("food_group", params.food_group);
  if (params?.is_veg) query.set("is_veg", params.is_veg);
  const qs = query.toString();
  return request<FoodItemListResponse>(`/food-items/${qs ? `?${qs}` : ""}`, { token });
}

export function createFoodItem(
  data: FoodItemFormData,
  token: string,
): Promise<FoodItem> {
  return request<FoodItem>("/food-items/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateFoodItem(
  id: number | string,
  data: FoodItemFormData,
  token: string,
): Promise<FoodItem> {
  return request<FoodItem>(`/food-items/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteFoodItem(id: number | string, token: string): Promise<void> {
  return request<void>(`/food-items/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* Diet plans */

export function fetchDietPlans(
  token: string,
  params?: { goal?: string; is_template?: string },
): Promise<DietPlanListResponse> {
  const query = new URLSearchParams();
  if (params?.goal) query.set("goal", params.goal);
  if (params?.is_template) query.set("is_template", params.is_template);
  const qs = query.toString();
  return request<DietPlanListResponse>(`/diet-plans/${qs ? `?${qs}` : ""}`, { token });
}

export function fetchDietPlan(
  id: number | string,
  token: string,
): Promise<DietPlan> {
  return request<DietPlan>(`/diet-plans/${id}/`, { token });
}

export function createDietPlan(
  data: DietPlanFormData,
  token: string,
): Promise<DietPlan> {
  return request<DietPlan>("/diet-plans/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateDietPlan(
  id: number | string,
  data: DietPlanFormData,
  token: string,
): Promise<DietPlan> {
  return request<DietPlan>(`/diet-plans/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteDietPlan(id: number | string, token: string): Promise<void> {
  return request<void>(`/diet-plans/${id}/`, {
    method: "DELETE",
    token,
  });
}

export function fetchDietPlanNutrition(
  id: number | string,
  token: string,
): Promise<NutritionBreakdown> {
  return request<NutritionBreakdown>(`/diet-plans/${id}/nutrition-breakdown/`, {
    token,
  });
}

export function duplicateDietPlan(
  id: number | string,
  token: string,
): Promise<DietPlan> {
  return request<DietPlan>(`/diet-plans/${id}/duplicate/`, {
    method: "POST",
    token,
  });
}

/* Diet assignments */

export function fetchDietAssignments(
  token: string,
  params?: { customer?: string; is_active?: string },
): Promise<DietAssignmentListResponse> {
  const query = new URLSearchParams();
  if (params?.customer) query.set("customer", params.customer);
  if (params?.is_active) query.set("is_active", params.is_active);
  const qs = query.toString();
  return request<DietAssignmentListResponse>(
    `/diet-assignments/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

export function assignDietPlan(
  data: DietAssignmentFormData,
  token: string,
): Promise<DietAssignment> {
  return request<DietAssignment>("/diet-assignments/", {
    method: "POST",
    body: data,
    token,
  });
}

/* ── Exercises ───────────────────────────────────────────────── */

import {
  Exercise,
  ExerciseCategory,
  ExerciseCategoryListResponse,
  ExerciseFilters,
  ExerciseFormData,
  ExerciseListResponse,
} from "@/types/exercise";

function buildQueryString(filters: ExerciseFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.muscle_group) params.set("muscle_group", filters.muscle_group);
  if (filters.equipment_needed) params.set("equipment_needed", filters.equipment_needed);
  if (filters.search) params.set("search", filters.search);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function fetchExerciseCategories(
  token: string,
): Promise<ExerciseCategoryListResponse> {
  return request<ExerciseCategoryListResponse>(
    "/exercises/exercise-categories/",
    { token },
  );
}

export function createExerciseCategory(
  data: { name: string; description?: string },
  token: string,
): Promise<ExerciseCategory> {
  return request<ExerciseCategory>("/exercises/exercise-categories/", {
    method: "POST",
    body: data,
    token,
  });
}

export function fetchExercises(
  token: string,
  filters: ExerciseFilters = {},
): Promise<ExerciseListResponse> {
  return request<ExerciseListResponse>(
    `/exercises/exercises/${buildQueryString(filters)}`,
    { token },
  );
}

export function fetchExercise(
  id: number | string,
  token: string,
): Promise<Exercise> {
  return request<Exercise>(`/exercises/exercises/${id}/`, { token });
}

export function createExercise(
  data: ExerciseFormData,
  token: string,
): Promise<Exercise> {
  return request<Exercise>("/exercises/exercises/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateExercise(
  id: number | string,
  data: ExerciseFormData,
  token: string,
): Promise<Exercise> {
  return request<Exercise>(`/exercises/exercises/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteExercise(
  id: number | string,
  token: string,
): Promise<void> {
  return request<void>(`/exercises/exercises/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* ── Feedback (FBOS-015) ─────────────────────────────────────── */

import {
  Feedback,
  FeedbackAnalytics,
  FeedbackFormData,
  FeedbackListResponse,
  FeedbackResponse as FeedbackResponseItem,
  FeedbackResponseFormData,
  FeedbackResponseListResponse,
  FeedbackResponseData,
  FeedbackSurvey,
  FeedbackSurveyFormData,
  FeedbackSurveyListResponse,
} from "@/types/feedback";

export function fetchFeedback(token: string): Promise<FeedbackListResponse> {
  return request<FeedbackListResponse>("/feedback/feedback/", { token });
}

export function createFeedback(
  data: FeedbackFormData,
  token: string,
): Promise<Feedback> {
  return request<Feedback>("/feedback/feedback/", {
    method: "POST",
    body: data,
    token,
  });
}

export function respondToFeedback(
  id: number | string,
  data: FeedbackResponseData,
  token: string,
): Promise<Feedback> {
  return request<Feedback>(`/feedback/feedback/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

export function fetchFeedbackAnalytics(token: string): Promise<FeedbackAnalytics> {
  return request<FeedbackAnalytics>("/feedback/feedback-analytics/", { token });
}

export function fetchFeedbackSurveys(
  token: string,
): Promise<FeedbackSurveyListResponse> {
  return request<FeedbackSurveyListResponse>("/feedback/feedback-surveys/", {
    token,
  });
}

export function createFeedbackSurvey(
  data: FeedbackSurveyFormData,
  token: string,
): Promise<FeedbackSurvey> {
  return request<FeedbackSurvey>("/feedback/feedback-surveys/", {
    method: "POST",
    body: data,
    token,
  });
}

export function fetchFeedbackResponses(
  token: string,
): Promise<FeedbackResponseListResponse> {
  return request<FeedbackResponseListResponse>("/feedback/feedback-responses/", {
    token,
  });
}

export function createFeedbackResponse(
  data: FeedbackResponseFormData,
  token: string,
): Promise<FeedbackResponseItem> {
  return request<FeedbackResponseItem>("/feedback/feedback-responses/", {
    method: "POST",
    body: data,
    token,
  });
}

/* ── Workouts (FBOS-012) ──────────────────────────────────────── */

import {
  WorkoutAssignment,
  WorkoutAssignmentFormData,
  WorkoutAssignmentListResponse,
  WorkoutLog,
  WorkoutLogFormData,
  WorkoutLogListResponse,
  WorkoutPlan,
  WorkoutPlanFormData,
  WorkoutPlanListResponse,
} from "@/types/workout";

/* Workout plans */

export function fetchWorkoutPlans(
  token: string,
  params?: { goal?: string; difficulty?: string; is_template?: string },
): Promise<WorkoutPlanListResponse> {
  const query = new URLSearchParams();
  if (params?.goal) query.set("goal", params.goal);
  if (params?.difficulty) query.set("difficulty", params.difficulty);
  if (params?.is_template) query.set("is_template", params.is_template);
  const qs = query.toString();
  return request<WorkoutPlanListResponse>(
    `/workouts/workout-plans/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

export function fetchWorkoutPlan(
  id: number | string,
  token: string,
): Promise<WorkoutPlan> {
  return request<WorkoutPlan>(`/workouts/workout-plans/${id}/`, { token });
}

export function createWorkoutPlan(
  data: WorkoutPlanFormData,
  token: string,
): Promise<WorkoutPlan> {
  return request<WorkoutPlan>("/workouts/workout-plans/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateWorkoutPlan(
  id: number | string,
  data: WorkoutPlanFormData,
  token: string,
): Promise<WorkoutPlan> {
  return request<WorkoutPlan>(`/workouts/workout-plans/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteWorkoutPlan(
  id: number | string,
  token: string,
): Promise<void> {
  return request<void>(`/workouts/workout-plans/${id}/`, {
    method: "DELETE",
    token,
  });
}

export function duplicateWorkoutPlan(
  id: number | string,
  token: string,
): Promise<WorkoutPlan> {
  return request<WorkoutPlan>(`/workouts/workout-plans/${id}/duplicate/`, {
    method: "POST",
    token,
  });
}

/* Workout assignments */

export function fetchWorkoutAssignments(
  token: string,
  params?: { customer?: string; is_active?: string },
): Promise<WorkoutAssignmentListResponse> {
  const query = new URLSearchParams();
  if (params?.customer) query.set("customer", params.customer);
  if (params?.is_active) query.set("is_active", params.is_active);
  const qs = query.toString();
  return request<WorkoutAssignmentListResponse>(
    `/workouts/workout-assignments/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

export function assignWorkoutPlan(
  data: WorkoutAssignmentFormData,
  token: string,
): Promise<WorkoutAssignment> {
  return request<WorkoutAssignment>("/workouts/workout-assignments/", {
    method: "POST",
    body: data,
    token,
  });
}

/* Workout logs */

export function fetchWorkoutLogs(
  token: string,
  params?: { customer?: string; date_from?: string; date_to?: string },
): Promise<WorkoutLogListResponse> {
  const query = new URLSearchParams();
  if (params?.customer) query.set("customer", params.customer);
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  return request<WorkoutLogListResponse>(
    `/workouts/workout-logs/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

export function createWorkoutLog(
  data: WorkoutLogFormData,
  token: string,
): Promise<WorkoutLog> {
  return request<WorkoutLog>("/workouts/workout-logs/", {
    method: "POST",
    body: data,
    token,
  });
}
/* ── Marketplace (FBOS-016) ───────────────────────────────────── */

import {
  Cart,
  MarketplaceProduct,
  MarketplaceProductListResponse,
  Order,
  OrderListResponse,
} from "@/types/marketplace";

export function fetchProducts(
  token: string,
  params?: { category?: string; search?: string },
): Promise<MarketplaceProductListResponse> {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return request<MarketplaceProductListResponse>(
    `/marketplace/products/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

export function fetchProduct(
  id: number | string,
  token: string,
): Promise<MarketplaceProduct> {
  return request<MarketplaceProduct>(`/marketplace/products/${id}/`, { token });
}

export function fetchCart(token: string): Promise<Cart> {
  return request<Cart>("/marketplace/cart/", { token });
}

export function addToCart(
  token: string,
  productId: number,
  quantity: number,
): Promise<Cart> {
  return request<Cart>("/marketplace/cart/", {
    method: "POST",
    body: { product: productId, quantity },
    token,
  });
}

export function fetchOrders(token: string): Promise<OrderListResponse> {
  return request<OrderListResponse>("/marketplace/orders/", { token });
}

export function fetchOrder(id: number | string, token: string): Promise<Order> {
  return request<Order>(`/marketplace/orders/${id}/`, { token });
}

/* ── AI Coach (FBOS-017) ────────────────────────────────────────── */

import {
  AiChatResponse,
  Conversation,
  ConversationListResponse,
} from "@/types/ai-coach";

export function aiChat(
  token: string,
  message: string,
  conversationId?: number,
): Promise<AiChatResponse> {
  return request<AiChatResponse>("/ai/coach/chat/", {
    method: "POST",
    body: { message, conversation_id: conversationId },
    token,
  });
}

export function fetchConversations(
  token: string,
): Promise<ConversationListResponse> {
  return request<ConversationListResponse>("/ai/coach/conversations/", { token });
}

/* ── AI Nutrition (FBOS-019) ────────────────────────────────────── */

import {
  GenerateMealPlanRequest,
  MealPlan,
  MealPlanListResponse,
  ShoppingList,
  ShoppingListResponse,
} from "@/types/nutrition";

export function fetchMealPlans(token: string): Promise<MealPlanListResponse> {
  return request<MealPlanListResponse>("/ai/nutrition/meal-plan/", { token });
}

export function fetchMealPlan(
  id: number | string,
  token: string,
): Promise<MealPlan> {
  return request<MealPlan>(`/ai/nutrition/meal-plan/${id}/`, { token });
}

export function generateMealPlan(
  token: string,
  preferences: GenerateMealPlanRequest,
): Promise<MealPlan> {
  return request<MealPlan>("/ai/nutrition/meal-plan/", {
    method: "POST",
    body: preferences,
    token,
  });
}

export function fetchShoppingList(token: string): Promise<ShoppingListResponse> {
  return request<ShoppingListResponse>("/ai/nutrition/shopping-list/", { token });
}

/* ── Branches (FBOS-023) ──────────────────────────────────────── */

import {
  Branch,
  BranchFormData,
  BranchListResponse,
} from "@/types/branch";

/* The branch list endpoint returns a plain array (no pagination). */
export function fetchBranches(token: string): Promise<BranchListResponse> {
  return request<BranchListResponse>("/branches/", { token });
}

export function fetchBranch(id: number | string, token: string): Promise<Branch> {
  return request<Branch>(`/branches/${id}/`, { token });
}

export function createBranch(
  data: BranchFormData,
  token: string,
): Promise<Branch> {
  return request<Branch>("/branches/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateBranch(
  id: number | string,
  data: Partial<BranchFormData>,
  token: string,
): Promise<Branch> {
  return request<Branch>(`/branches/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Delete a branch.
 * NOTE: The Sprint 1 backend does not yet expose a DELETE endpoint. This
 * function targets `DELETE /branches/{id}/` and will surface a 405 until
 * Forge adds it. Flagged as an open gap for FBOS-023.
 */
export function deleteBranch(
  id: number | string,
  token: string,
): Promise<void> {
  return request<void>(`/branches/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* ── Trainer performance (FBOS-024) ───────────────────────────── */

import {
  TrainerMetrics,
  TrainerPerformanceDetail,
  TrainerPerformanceListResponse,
} from "@/types/trainer-performance";

/** List monthly trainer performance snapshots (plain array, no pagination). */
export function fetchTrainerPerformance(
  token: string,
): Promise<TrainerPerformanceListResponse> {
  return request<TrainerPerformanceListResponse>("/trainer-performance/", {
    token,
  });
}

/** Fetch aggregated performance + monthly series for a single trainer. */
export function fetchTrainerPerformanceDetail(
  id: number | string,
  token: string,
): Promise<TrainerPerformanceDetail> {
  return request<TrainerPerformanceDetail>(`/trainers/${id}/performance/`, {
    token,
  });
}

/** Fetch live metrics (active clients, utilization) for a single trainer. */
export function fetchTrainerMetrics(
  id: number | string,
  token: string,
): Promise<TrainerMetrics> {
  return request<TrainerMetrics>(`/users/trainers/${id}/metrics/`, {
    token,
  });
}

/* ── Wati notifications (FBOS-022) ────────────────────────────── */

import {
  NotificationLog,
  NotificationLogListResponse,
  NotificationStatus,
  NotificationType,
  TestNotificationResult,
  WatiSettings,
  WatiSettingsUpdate,
} from "@/types/notification";

/** Fetch the tenant's current Wati configuration. */
export function fetchNotificationSettings(
  token: string,
): Promise<WatiSettings> {
  return request<WatiSettings>("/notifications/settings/", { token });
}

/** Update the tenant's Wati configuration. */
export function updateNotificationSettings(
  data: WatiSettingsUpdate,
  token: string,
): Promise<WatiSettings> {
  return request<WatiSettings>("/notifications/settings/", {
    method: "PATCH",
    body: data,
    token,
  });
}

/** Send a test WhatsApp message to verify Wati connectivity. */
export function sendTestNotification(
  data: { to: string; message?: string; notification_type?: NotificationType },
  token: string,
): Promise<TestNotificationResult> {
  return request<TestNotificationResult>("/notifications/test/", {
    method: "POST",
    body: data,
    token,
  });
}

/** List notification logs, optionally filtered by status and/or type. */
export function fetchNotificationLogs(
  token: string,
  params?: { status?: NotificationStatus; notification_type?: NotificationType },
): Promise<NotificationLogListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.notification_type) query.set("notification_type", params.notification_type);
  const qs = query.toString();
  return request<NotificationLogListResponse>(
    `/notifications/logs/${qs ? `?${qs}` : ""}`,
    { token },
  );
}

/**
 * Helper that normalises a raw paginated response into an array, tolerating
 * plain-array responses from endpoints that skip DRF pagination.
 */
export function unwrapNotificationLogs(
  res: NotificationLogListResponse | NotificationLog[],
): NotificationLog[] {
  return unwrapList(res);
}

/* ── Customer detail sub-resources (FBOS-025) ─────────────────── */

import {
  BodyMeasurement,
  BodyMeasurementFormData,
  CustomerFitnessGoal,
  FitnessGoalFormData,
  HealthProfile,
  HealthProfileUpdate,
  ProgressPhoto,
  ProgressPhotoFormData,
  ProgressSummary,
} from "@/types/customer-detail";

/** List fitness goals for a customer (plain array). */
export function fetchFitnessGoals(
  id: number | string,
  token: string,
): Promise<CustomerFitnessGoal[]> {
  return request<CustomerFitnessGoal[]>(
    `/customers/customers/${id}/fitness-goals/`,
    { token },
  );
}

/** Create a fitness goal for a customer. */
export function createFitnessGoal(
  id: number | string,
  data: FitnessGoalFormData,
  token: string,
): Promise<CustomerFitnessGoal> {
  return request<CustomerFitnessGoal>(
    `/customers/customers/${id}/fitness-goals/`,
    {
      method: "POST",
      body: data,
      token,
    },
  );
}

/** List body measurements for a customer (plain array). */
export function fetchBodyMeasurements(
  id: number | string,
  token: string,
): Promise<BodyMeasurement[]> {
  // The flat BodyMeasurementViewSet paginates (PageNumberPagination) -
  // unwrap the {count, next, previous, results} envelope into a plain
  // array so the tab can iterate it directly.
  return request<BodyMeasurement[] | { results?: BodyMeasurement[] }>(
    `/customers/body-measurements/?customer=${id}`,
    { token },
  ).then(unwrapList);
}

/** Create a body measurement for a customer. */
export function createBodyMeasurement(
  id: number | string,
  data: BodyMeasurementFormData,
  token: string,
): Promise<BodyMeasurement> {
  return request<BodyMeasurement>(`/customers/body-measurements/`, {
    method: "POST",
    body: { customer: id, ...data },
    token,
  });
}

/** Fetch the customer's health profile. */
export function fetchHealthProfile(
  id: number | string,
  token: string,
): Promise<HealthProfile> {
  return request<HealthProfile>(
    `/customers/customers/${id}/health-profile/`,
    { token },
  );
}

/** Update the customer's health profile. */
export function updateCustomerHealthProfile(
  id: number | string,
  data: HealthProfileUpdate,
  token: string,
): Promise<HealthProfile> {
  return request<HealthProfile>(
    `/customers/customers/${id}/health-profile/`,
    {
      method: "PATCH",
      body: data,
      token,
    },
  );
}

/** Update an existing fitness goal for a customer. */
export function updateFitnessGoal(
  id: number | string,
  goalId: number | string,
  data: Partial<FitnessGoalFormData>,
  token: string,
): Promise<CustomerFitnessGoal> {
  return request<CustomerFitnessGoal>(`/customers/fitness-goals/${goalId}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/** List progress photos for a customer (plain array). */
export function fetchProgressPhotos(
  id: number | string,
  token: string,
): Promise<ProgressPhoto[]> {
  return request<ProgressPhoto[]>(
    `/customers/customers/${id}/progress-photos/`,
    { token },
  );
}

/** Create a progress photo for a customer. */
export function createProgressPhoto(
  id: number | string,
  data: ProgressPhotoFormData,
  token: string,
): Promise<ProgressPhoto> {
  return request<ProgressPhoto>(
    `/customers/customers/${id}/progress-photos/`,
    {
      method: "POST",
      body: data,
      token,
    },
  );
}

/** Fetch the aggregated progress summary for a customer. */
export function fetchProgressSummary(
  id: number | string,
  token: string,
): Promise<ProgressSummary> {
  return request<ProgressSummary>(
    `/customers/customers/${id}/progress-summary/`,
    { token },
  );
}

/* ── Access control (Sprint 8: issues #23, #25, #26) ──────────── */

import {
  AccessCredential,
  AccessDevice,
  AccessDeviceFormData,
  AccessLog,
  AccessOverride,
  AccessOverrideFormData,
  DeviceEventsResult,
  DeviceSyncResult,
  DeviceTestResult,
  EnrollCredentialData,
  EnrollCredentialResult,
} from "@/types/access";

/** Build the query string shared by the access list endpoints. */
function buildAccessQuery(
  params?: { device?: number | string; customer?: number | string },
): string {
  const query = new URLSearchParams();
  if (params?.device !== undefined && params?.device !== "") {
    query.set("device", String(params.device));
  }
  if (params?.customer !== undefined && params?.customer !== "") {
    query.set("customer", String(params.customer));
  }
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

/* Devices */

export function fetchDevices(
  token: string,
  params?: { branch?: number | string },
): Promise<AccessDevice[]> {
  const query = new URLSearchParams();
  if (params?.branch !== undefined && params?.branch !== "") {
    query.set("branch", String(params.branch));
  }
  const qs = query.toString();
  return request<AccessDevice[] | { results?: AccessDevice[] }>(
    `/access/devices/${qs ? `?${qs}` : ""}`,
    { token },
  ).then(unwrapList);
}

export function createDevice(
  data: AccessDeviceFormData,
  token: string,
): Promise<AccessDevice> {
  return request<AccessDevice>("/access/devices/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateDevice(
  id: number | string,
  data: Partial<AccessDeviceFormData>,
  token: string,
): Promise<AccessDevice> {
  return request<AccessDevice>(`/access/devices/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Remove a device from the registry (DELETE /access/devices/{id}/).
 * The backend may refuse when attendance logs, credentials, or queued
 * commands still reference the device — the error detail is surfaced 1:1.
 */
export function deleteDevice(
  id: number | string,
  token: string,
): Promise<void> {
  return request<void>(`/access/devices/${id}/`, {
    method: "DELETE",
    token,
  });
}

/** Run the vendor adapter connection test against a device. */
export function testDeviceConnection(
  id: number | string,
  token: string,
): Promise<DeviceTestResult> {
  return request<DeviceTestResult>(`/access/devices/${id}/test-connection/`, {
    method: "POST",
    token,
  });
}

/** Force an allow-list sync for a device now. */
export function syncDevice(
  id: number | string,
  token: string,
): Promise<DeviceSyncResult> {
  return request<DeviceSyncResult>(`/access/devices/${id}/sync/`, {
    method: "POST",
    token,
  });
}

/** Pull entry/exit events from a device and record them as logs. */
export function fetchDeviceEvents(
  id: number | string,
  token: string,
): Promise<DeviceEventsResult> {
  return request<DeviceEventsResult>(`/access/devices/${id}/fetch-events/`, {
    method: "POST",
    token,
  });
}

/* Credentials (enrollment records) */

/** Enroll a biometric credential on a device and immediately sync it. */
export function enrollBiometricCredential(
  data: EnrollCredentialData,
  token: string,
): Promise<EnrollCredentialResult> {
  return request<EnrollCredentialResult>("/access/devices/enroll/", {
    method: "POST",
    body: data,
    token,
  });
}

export function fetchAccessCredentials(
  token: string,
  params?: { device?: number | string; customer?: number | string },
): Promise<AccessCredential[]> {
  return request<AccessCredential[] | { results?: AccessCredential[] }>(
    `/access/credentials/${buildAccessQuery(params)}`,
    { token },
  ).then(unwrapList);
}

/**
 * Deactivate a credential (POST /access/credentials/{id}/deactivate/) —
 * the customer stops resolving on punches for that device.
 */
export function deactivateBiometricCredential(
  id: number | string,
  token: string,
): Promise<AccessCredential> {
  return request<AccessCredential>(`/access/credentials/${id}/deactivate/`, {
    method: "POST",
    token,
  });
}

/* Owner overrides */

export function fetchAccessOverrides(
  token: string,
  params?: { device?: number | string; customer?: number | string },
): Promise<AccessOverride[]> {
  return request<AccessOverride[] | { results?: AccessOverride[] }>(
    `/access/overrides/${buildAccessQuery(params)}`,
    { token },
  ).then(unwrapList);
}

export function createAccessOverride(
  data: AccessOverrideFormData,
  token: string,
): Promise<AccessOverride> {
  return request<AccessOverride>("/access/overrides/", {
    method: "POST",
    body: data,
    token,
  });
}

/* Access logs (entry/exit history) */

export function fetchAccessLogs(
  token: string,
  params?: { device?: number | string; customer?: number | string },
): Promise<AccessLog[]> {
  return request<AccessLog[] | { results?: AccessLog[] }>(
    `/access/logs/${buildAccessQuery(params)}`,
    { token },
  ).then(unwrapList);
}

/* ── Equipment & inventory (Sprint 6 residual, issue #6) ──────── */

import {
  Equipment,
  EquipmentFormData,
  InventoryItem,
  InventoryItemFormData,
  MaintenanceLog,
  MaintenanceLogFormData,
} from "@/types/inventory";

/* Equipment */

export function fetchEquipment(token: string): Promise<Equipment[]> {
  return request<Equipment[] | { results?: Equipment[] }>(
    "/inventory/equipment/",
    { token },
  ).then(unwrapList);
}

export function createEquipment(
  data: EquipmentFormData,
  token: string,
): Promise<Equipment> {
  return request<Equipment>("/inventory/equipment/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateEquipment(
  id: number | string,
  data: Partial<EquipmentFormData>,
  token: string,
): Promise<Equipment> {
  return request<Equipment>(`/inventory/equipment/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

export function deleteEquipment(
  id: number | string,
  token: string,
): Promise<void> {
  return request<void>(`/inventory/equipment/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* Inventory items (stock per equipment) */

export function fetchInventoryItems(token: string): Promise<InventoryItem[]> {
  return request<InventoryItem[] | { results?: InventoryItem[] }>(
    "/inventory/inventory-items/",
    { token },
  ).then(unwrapList);
}

export function createInventoryItem(
  data: InventoryItemFormData,
  token: string,
): Promise<InventoryItem> {
  return request<InventoryItem>("/inventory/inventory-items/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateInventoryItem(
  id: number | string,
  data: Partial<InventoryItemFormData>,
  token: string,
): Promise<InventoryItem> {
  return request<InventoryItem>(`/inventory/inventory-items/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/* Maintenance logs */

export function fetchMaintenanceLogs(token: string): Promise<MaintenanceLog[]> {
  return request<MaintenanceLog[] | { results?: MaintenanceLog[] }>(
    "/inventory/maintenance-logs/",
    { token },
  ).then(unwrapList);
}

export function createMaintenanceLog(
  data: MaintenanceLogFormData,
  token: string,
): Promise<MaintenanceLog> {
  return request<MaintenanceLog>("/inventory/maintenance-logs/", {
    method: "POST",
    body: data,
    token,
  });
}

/* ── Reviews & ratings (Sprint 6 residual, issue #7) ──────────── */

import {
  Review,
  ReviewFormData,
  ReviewListEnvelope,
  ReviewRespondData,
} from "@/types/reviews";

export function fetchReviews(
  token: string,
  params?: { branch_id?: number | string },
): Promise<ReviewListEnvelope> {
  const query = new URLSearchParams();
  if (params?.branch_id !== undefined && params?.branch_id !== "") {
    query.set("branch_id", String(params.branch_id));
  }
  const qs = query.toString();
  return request<ReviewListEnvelope>(`/reviews/${qs ? `?${qs}` : ""}`, {
    token,
  });
}

export function createReview(
  data: ReviewFormData,
  token: string,
): Promise<Review> {
  return request<Review>("/reviews/", {
    method: "POST",
    body: data,
    token,
  });
}

export function respondToReview(
  id: number | string,
  data: ReviewRespondData,
  token: string,
): Promise<unknown> {
  return request<unknown>(`/reviews/${id}/respond/`, {
    method: "POST",
    body: data,
    token,
  });
}

/* ── Platform admin (Sprint 10, issues #39/#41/#42/#43-#47) ────── */

import {
  AdminOnboardGymFormData,
  AdminOnboardGymResult,
  AdminPlanFormData,
  AdminRotateCredentialsResult,
  AdminSubscriptionPlan,
  AdminTenant,
  AdminTenantUpdateFormData,
  AdminTenantSwitchStatus,
  ImpersonateTenantResult,
} from "@/types/admin";

export function fetchAdminTenants(token: string): Promise<AdminTenant[]> {
  return request<AdminTenant[] | { results?: AdminTenant[] }>(
    "/admin/tenants/",
    { token },
  ).then(unwrapList);
}

export function onboardGym(
  data: AdminOnboardGymFormData,
  token: string,
): Promise<AdminOnboardGymResult> {
  return request<AdminOnboardGymResult>("/admin/tenants/onboard/", {
    method: "POST",
    body: data,
    token,
  });
}

/** Partially update a gym — edit fields and/or suspend/reactivate. */
export function updateAdminTenant(
  id: number | string,
  data: AdminTenantUpdateFormData,
  token: string,
): Promise<AdminTenant> {
  return request<AdminTenant>(`/admin/tenants/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Generate a new password for a gym owner. The plaintext password comes
 * back exactly once for handover and is never retrievable again; all of
 * the owner's active sessions are logged out.
 */
export function rotateAdminTenantCredentials(
  id: number | string,
  token: string,
): Promise<AdminRotateCredentialsResult> {
  return request<AdminRotateCredentialsResult>(
    `/admin/tenants/${id}/rotate-credentials/`,
    { method: "POST", token },
  );
}

/**
 * Archive a gym (soft delete — status becomes "archived"). There is no
 * un-archive endpoint, so this is not reversible from the UI.
 */
export function deleteAdminTenant(
  id: number | string,
  token: string,
): Promise<AdminTenant> {
  return request<AdminTenant>(`/admin/tenants/${id}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Start a 30-minute impersonated owner session (issue #45). The action is
 * recorded in the backend impersonation audit log (who, when, which gym).
 */
export function impersonateTenant(
  id: number | string,
  token: string,
): Promise<ImpersonateTenantResult> {
  return request<ImpersonateTenantResult>(`/admin/tenants/${id}/impersonate/`, {
    method: "POST",
    token,
  });
}

/* ── Platform admin: subscription plans (issue #44) ────────────── */

/** Every plan including inactive ones (catalog order). */
export function fetchAdminPlans(token: string): Promise<AdminSubscriptionPlan[]> {
  return request<AdminSubscriptionPlan[] | { results?: AdminSubscriptionPlan[] }>(
    "/admin/plans/",
    { token },
  ).then(unwrapList);
}

export function createAdminPlan(
  data: AdminPlanFormData,
  token: string,
): Promise<AdminSubscriptionPlan> {
  return request<AdminSubscriptionPlan>("/admin/plans/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateAdminPlan(
  id: number | string,
  data: Partial<AdminPlanFormData>,
  token: string,
): Promise<AdminSubscriptionPlan> {
  return request<AdminSubscriptionPlan>(`/admin/plans/${id}/`, {
    method: "PATCH",
    body: data,
    token,
  });
}

/**
 * Deactivate a plan (soft delete — the row stays so historical tenants
 * keep a resolvable plan code). Returns the plan with is_active=false.
 */
export function deactivateAdminPlan(
  id: number | string,
  token: string,
): Promise<AdminSubscriptionPlan> {
  return request<AdminSubscriptionPlan>(`/admin/plans/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* ── App access & invites (FBOS-011) ──────────────────────────── */

import {
  AppInviteBlock,
  OnboardingMemberPayload,
  OnboardingResult,
  OnboardingVerifyPaymentPayload,
} from "@/types/onboarding";

/**
 * Front-desk phone lookup for the onboarding wizard (searches name, phone,
 * email — backend `search_fields`). Returns a plain array on either backend
 * list shape via unwrapList.
 */
export function searchCustomers(token: string, search: string): Promise<Customer[]> {
  const query = new URLSearchParams({ search });
  return request<Customer[] | { results?: Customer[] }>(
    `/customers/customers/?${query.toString()}`,
    { token },
  ).then(unwrapList);
}

/**
 * One-shot member onboarding (POST /onboarding/member/). The optional
 * idempotency key is the double-submit guard the backend replays on
 * (OnboardingSession lookup).
 */
export function onboardMember(
  payload: OnboardingMemberPayload,
  token: string,
  idempotencyKey?: string,
): Promise<OnboardingResult> {
  return request<OnboardingResult>("/onboarding/member/", {
    method: "POST",
    body: payload,
    token,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
  });
}

/** Razorpay phase 2 for the onboarding wizard. */
export function verifyOnboardingPayment(
  onboardingId: string,
  payload: OnboardingVerifyPaymentPayload,
  token: string,
): Promise<OnboardingResult> {
  return request<OnboardingResult>(
    `/onboarding/member/${onboardingId}/verify-payment/`,
    { method: "POST", body: payload, token },
  );
}

/**
 * Send / resend the mobile-app invite (POST /memberships/app-invite/).
 * Fresh send → status "sent"; inside the 24 h dedupe window → "already_sent"
 * (pass `resend: true` to force). `not_applicable` means the plan/tenant
 * flag excludes the app; `failed`/`skipped` are retryable.
 */
export function sendAppInvite(
  customerId: number,
  token: string,
  resend = false,
): Promise<AppInviteBlock> {
  return request<AppInviteBlock>("/memberships/app-invite/", {
    method: "POST",
    body: { customer_id: customerId, resend },
    token,
  });
}

/* ── Tenant WhatsApp (WATI) configuration — FBOS-011 §6 ────────── */

/** WATI fields on the tenant payload (write-only key, masked read). */
export interface TenantWhatsappConfig {
  is_wati_enabled: boolean;
  wati_endpoint: string;
  /** Read state only: whether a key is configured — never the secret. */
  wati_api_key_configured: boolean;
}

/** Gupshup fields on the tenant payload (issue #66/#67) — same masked pattern as WATI. */
export interface TenantGupshupConfig {
  is_gupshup_enabled: boolean;
  /** Sender/source identifier (phone number or source string) from Gupshup. */
  gupshup_source: string;
  /** Gupshup app (data bot) name messages are sent through. */
  gupshup_app_name: string;
  /** Read state only: whether a key is configured — never the secret. */
  gupshup_api_key_configured: boolean;
}

/** Usage counters for the settings page (today's sends + budget). */
export interface WhatsappStatus {
  otp_sent_today: number;
  invites_sent_today: number;
  daily_cap: number;
}

export interface WhatsappTestResult {
  status: string;
  detail?: string;
}

/** Current tenant payload (GET /tenants/me/). Channel fields may be absent pre-#66. */
export type TenantMe = Partial<TenantWhatsappConfig & TenantGupshupConfig> & {
  /** Short code members type during gym lookup on app install (issue #60). */
  gym_code?: string | null;
};

/** Current tenant (GET /tenants/me/). */
export function fetchTenant(token: string): Promise<TenantMe> {
  return request<TenantMe>("/tenants/me/", { token });
}

/**
 * Save the WhatsApp config (PATCH /tenants/me/ — FBOS-011 §6 / task B9).
 * The API key is write-only: only include it when the owner typed a new one;
 * the backend keeps the stored secret otherwise.
 */
export function updateTenantWhatsappConfig(
  payload: { is_wati_enabled: boolean; wati_endpoint: string; wati_api_key?: string },
  token: string,
): Promise<Partial<TenantWhatsappConfig>> {
  return request<Partial<TenantWhatsappConfig>>("/tenants/me/", {
    method: "PATCH",
    body: payload,
    token,
  });
}

/**
 * Save the Gupshup config (PATCH /tenants/me/ — issue #66/#67).
 * The API key is write-only: only include it when the owner typed a new one;
 * the backend keeps the stored secret otherwise.
 */
export function updateTenantGupshupConfig(
  payload: {
    is_gupshup_enabled: boolean;
    gupshup_source: string;
    gupshup_app_name: string;
    gupshup_api_key?: string;
  },
  token: string,
): Promise<Partial<TenantGupshupConfig>> {
  return request<Partial<TenantGupshupConfig>>("/tenants/me/", {
    method: "PATCH",
    body: payload,
    token,
  });
}

/**
 * Send the welcome-template test message to a phone (POST /tenants/whatsapp/test/).
 * ``provider`` selects the WhatsApp BSP under test (issue #66/#67) — default
 * "wati" keeps the pre-#66 call sites unchanged.
 */
export function sendWhatsappTest(
  phone: string,
  token: string,
  provider: "wati" | "gupshup" = "wati",
): Promise<WhatsappTestResult> {
  return request<WhatsappTestResult>("/tenants/whatsapp/test/", {
    method: "POST",
    body: { phone, provider },
    token,
  });
}

/** Today's OTP + invite counts vs the per-tenant cap (GET /tenants/whatsapp/status/). */
export function fetchWhatsappStatus(token: string): Promise<WhatsappStatus> {
  return request<WhatsappStatus>("/tenants/whatsapp/status/", { token });
}

/** Suspend or reactivate a gym (issue #43). Returns the updated tenant. */
export function updateAdminTenantStatus(
  id: number | string,
  status: AdminTenantSwitchStatus,
  token: string,
): Promise<AdminTenant> {
  return request<AdminTenant>(`/admin/tenants/${id}/`, {
    method: "PATCH",
    body: { status },
    token,
  });
}

/* ── Tenant module feature flags (issues #46/#63) ──────────────── */

/** One toggleable module from the settings catalog. */
export interface ModuleFeatureMeta {
  key: string;
  /** Settings-page display name. */
  label: string;
  description: string;
  /** Value seeded for new tenants; re-enabling resets to this. */
  default: boolean;
}

/** Resolved module flags + toggle catalog (GET /tenants/features/). */
export interface TenantFeatureSettings {
  flags: Record<string, boolean>;
  catalog: ModuleFeatureMeta[];
}

/** Read the gym's module toggles (any tenant member). */
export function fetchTenantFeatureSettings(
  token: string,
): Promise<TenantFeatureSettings> {
  return request<TenantFeatureSettings>("/tenants/features/", { token });
}

/**
 * Merge module-flag overrides (PATCH /tenants/features/ — owner-only).
 * Partial: only the given keys change; the response carries the refreshed
 * flags + catalog after persistence.
 */
export function updateTenantFeatureFlags(
  flags: Record<string, boolean>,
  token: string,
): Promise<TenantFeatureSettings> {
  return request<TenantFeatureSettings>("/tenants/features/", {
    method: "PATCH",
    body: { flags },
    token,
  });
}
