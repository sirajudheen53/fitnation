/**
 * FBOS-009: Frontend Route Guards & Permission Helpers
 *
 * Maps roles to permission sets and provides utilities for
 * checking permissions in components and protecting routes.
 */

// ── Role types ──────────────────────────────────────────────────

export type UserRole =
  | "platform_admin"
  | "gym_owner"
  | "manager"
  | "trainer"
  | "dietitian"
  | "customer";

export interface PermissionUser {
  role: string;
  permissions?: string[];
}

// ── Permission matrix ───────────────────────────────────────────

export const ROLE_PERMISSIONS: Record<string, Set<string>> = {
  platform_admin: new Set(["*"]),
  gym_owner: new Set(["*"]),
  manager: new Set([
    "branches.view_branch",
    "customers.view_customer",
    "customers.create_customer",
    "customers.edit_customer",
    "users.view_user",
    "users.create_user",
    "users.edit_user",
    "memberships.view_membership",
    "memberships.create_membership",
    "memberships.edit_membership",
    "payments.view_payment",
    "payments.record_payment",
    "attendance.view_attendance",
    "attendance.log_attendance",
    "dashboard.view_dashboard",
    "reports.view_report",
  ]),
  trainer: new Set([
    "customers.view_customer",
    "memberships.view_membership",
    "attendance.view_attendance",
    "attendance.log_attendance",
    "workouts.view_workout",
    "workouts.create_workout",
    "workouts.edit_workout",
    "dashboard.view_dashboard",
  ]),
  dietitian: new Set([
    "customers.view_customer",
    "diets.view_diet",
    "diets.create_diet",
    "diets.edit_diet",
  ]),
  customer: new Set([
    "memberships.view_membership",
    "payments.view_payment",
    "attendance.view_attendance",
    "attendance.log_attendance",
    "workouts.view_workout",
    "diets.view_diet",
  ]),
};

// ── Permission helpers ──────────────────────────────────────────

export function hasPermission(userRole: string, permission: string): boolean {
  const perms = ROLE_PERMISSIONS[userRole];
  if (!perms) return false;
  if (perms.has("*")) return true;
  return perms.has(permission);
}

export function hasAnyPermission(userRole: string, permissions: string[]): boolean {
  return permissions.some((p) => hasPermission(userRole, p));
}

export function hasAllPermissions(userRole: string, permissions: string[]): boolean {
  return permissions.every((p) => hasPermission(userRole, p));
}

// ── Route guard map ─────────────────────────────────────────────

export const ROUTE_PERMISSIONS: Record<string, string[]> = {
  "/dashboard": ["dashboard.view_dashboard"],
  "/branches": ["branches.view_branch"],
  "/branches/new": ["branches.create_branch"],
  "/customers": ["customers.view_customer"],
  "/customers/new": ["customers.create_customer"],
  "/memberships": ["memberships.view_membership"],
  "/payments": ["payments.view_payment"],
  "/attendance": ["attendance.view_attendance"],
  "/workouts": ["workouts.view_workout"],
  "/diets": ["diets.view_diet"],
  "/users": ["users.view_user"],
  "/reports": ["reports.view_report"],
  "/settings": ["tenants.edit_tenant"],
};

export function canAccessRoute(userRole: string, pathname: string): boolean {
  const required = ROUTE_PERMISSIONS[pathname];
  if (!required) return true; // no permission needed
  return hasAnyPermission(userRole, required);
}

// ── Role display helpers ────────────────────────────────────────

export const ROLE_LABELS: Record<UserRole, string> = {
  platform_admin: "Platform Admin",
  gym_owner: "Gym Owner",
  manager: "Manager",
  trainer: "Trainer",
  dietitian: "Dietitian",
  customer: "Customer",
};

export const ROLE_COLORS: Record<UserRole, string> = {
  platform_admin: "bg-purple-100 text-purple-800",
  gym_owner: "bg-indigo-100 text-indigo-800",
  manager: "bg-blue-100 text-blue-800",
  trainer: "bg-green-100 text-green-800",
  dietitian: "bg-orange-100 text-orange-800",
  customer: "bg-gray-100 text-gray-800",
};

export function getRoleLabel(role: string): string {
  return ROLE_LABELS[role as UserRole] ?? role;
}

export function getRoleColor(role: string): string {
  return ROLE_COLORS[role as UserRole] ?? "bg-gray-100 text-gray-800";
}