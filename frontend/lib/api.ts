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
  return request<MembershipPlanListResponse>("/memberships/plans/", { token });
}

export function fetchMembershipPlan(
  id: number | string,
  token: string,
): Promise<MembershipPlan> {
  return request<MembershipPlan>(`/memberships/plans/${id}/`, { token });
}

export function createMembershipPlan(
  data: MembershipPlanFormData,
  token: string,
): Promise<MembershipPlan> {
  return request<MembershipPlan>("/memberships/plans/", {
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
  return request<MembershipPlan>(`/memberships/plans/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteMembershipPlan(id: number | string, token: string): Promise<void> {
  return request<void>(`/memberships/plans/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* Active memberships */

export function fetchMemberships(token: string): Promise<MembershipListResponse> {
  return request<MembershipListResponse>("/memberships/memberships/", { token });
}

export function assignMembership(
  data: AssignMembershipData,
  token: string,
): Promise<Membership> {
  return request<Membership>("/memberships/memberships/", {
    method: "POST",
    body: data,
    token,
  });
}

export function cancelMembership(id: number | string, token: string): Promise<Membership> {
  return request<Membership>(`/memberships/memberships/${id}/cancel/`, {
    method: "POST",
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
  PaymentListResponse,
  RevenueSummary,
} from "@/types/payment";

export function fetchPayments(token: string): Promise<PaymentListResponse> {
  return request<PaymentListResponse>("/payments/payments/", { token });
}

export function fetchPayment(id: number | string, token: string): Promise<Payment> {
  return request<Payment>(`/payments/payments/${id}/`, { token });
}

export function createPayment(data: PaymentFormData, token: string): Promise<Payment> {
  return request<Payment>("/payments/payments/", {
    method: "POST",
    body: data,
    token,
  });
}

export function fetchRevenueSummary(token: string): Promise<RevenueSummary> {
  return request<RevenueSummary>("/payments/revenue-summary/", { token });
}

/* Invoices */

export function fetchInvoices(token: string): Promise<InvoiceListResponse> {
  return request<InvoiceListResponse>("/invoices/invoices/", { token });
}

export function fetchInvoice(id: number | string, token: string): Promise<Invoice> {
  return request<Invoice>(`/invoices/invoices/${id}/`, { token });
}

/* ── Attendance ───────────────────────────────────────────────── */

import {
  AttendanceListResponse,
  AttendanceRecord,
  AttendanceStatsResponse,
  CheckInData,
} from "@/types/attendance";

export function fetchAttendance(token: string): Promise<AttendanceListResponse> {
  return request<AttendanceListResponse>("/attendance/records/", { token });
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
  return request<AttendanceRecord>(`/attendance/records/${id}/check-out/`, {
    method: "POST",
    token,
  });
}

/* ── Trainers ─────────────────────────────────────────────────── */

import {
  AssignmentFormData,
  AssignmentListResponse,
  ScheduleListResponse,
  ScheduleSlot,
  Trainer,
  TrainerAssignment,
  TrainerFormData,
  TrainerListResponse,
} from "@/types/trainer";

export function fetchTrainers(token: string): Promise<TrainerListResponse> {
  return request<TrainerListResponse>("/trainers/trainers/", { token });
}

export function fetchTrainer(id: number | string, token: string): Promise<Trainer> {
  return request<Trainer>(`/trainers/trainers/${id}/`, { token });
}

export function createTrainer(data: TrainerFormData, token: string): Promise<Trainer> {
  return request<Trainer>("/trainers/trainers/", {
    method: "POST",
    body: data,
    token,
  });
}

export function updateTrainer(
  id: number | string,
  data: TrainerFormData,
  token: string,
): Promise<Trainer> {
  return request<Trainer>(`/trainers/trainers/${id}/`, {
    method: "PUT",
    body: data,
    token,
  });
}

export function deleteTrainer(id: number | string, token: string): Promise<void> {
  return request<void>(`/trainers/trainers/${id}/`, {
    method: "DELETE",
    token,
  });
}

/* Assignments */

export function fetchAssignments(token: string): Promise<AssignmentListResponse> {
  return request<AssignmentListResponse>("/trainers/assignments/", { token });
}

export function assignTrainer(
  data: AssignmentFormData,
  token: string,
): Promise<TrainerAssignment> {
  return request<TrainerAssignment>("/trainers/assignments/", {
    method: "POST",
    body: data,
    token,
  });
}

/* Schedule */

export function fetchSchedule(token: string): Promise<ScheduleListResponse> {
  return request<ScheduleListResponse>("/trainers/schedule/", { token });
}

export function createScheduleSlot(
  data: Omit<ScheduleSlot, "id" | "trainer_name">,
  token: string,
): Promise<ScheduleSlot> {
  return request<ScheduleSlot>("/trainers/schedule/", {
    method: "POST",
    body: data,
    token,
  });
}

/* ── Dashboard ────────────────────────────────────────────────── */

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

export function fetchDashboardTrainers(token: string): Promise<TrainerOverviewData[]> {
  return request<TrainerOverviewData[]>("/dashboard/trainers/", { token });
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
  return request<Cart>("/marketplace/cart/items/", {
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
  return Array.isArray(res) ? res : (res.results ?? []);
}
