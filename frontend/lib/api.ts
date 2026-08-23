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
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "An unexpected error occurred.";
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string;
  headers?: Record<string, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, headers = {} } = options;

  const config: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  if (token) {
    config.headers = { ...config.headers, Authorization: `Token ${token}` };
  }

  if (body !== undefined) {
    config.body = JSON.stringify(body);
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

export function createCustomer(
  data: CustomerFormData,
  token: string,
): Promise<Customer> {
  return request<Customer>("/customers/customers/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateCustomer(
  id: number | string,
  data: CustomerFormData,
  token: string,
): Promise<Customer> {
  return request<Customer>(`/customers/customers/${id}/`, {
    method: "PUT",
    body: data,
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

export function login(data: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login/", {
    method: "POST",
    body: data,
  });
}