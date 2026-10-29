/**
 * #92: Human-readable presentation for permission codes.
 *
 * The RBAC matrix (`lib/permissions.ts`) speaks in codes like
 * `customers.view_customer`. Owners read labels like "View customers",
 * grouped by product area. Label names follow the backend's canonical
 * permission registry (`seed_permissions.py`), gym-ified where the raw
 * wording is tenant-speak ("tenant" → "gym settings").
 */

import { ROLE_PERMISSIONS } from "@/lib/permissions";

/** Canonical label per permission code; falls back to humanizing the code. */
export const PERMISSION_LABELS: Record<string, string> = {
  "dashboard.view_dashboard": "View dashboard",
  "reports.view_report": "View reports",
  "branches.view_branch": "View branches",
  "branches.create_branch": "Create branches",
  "branches.edit_branch": "Edit branches",
  "branches.delete_branch": "Delete branches",
  "customers.view_customer": "View customers",
  "customers.create_customer": "Add customers",
  "customers.edit_customer": "Edit customers",
  "customers.delete_customer": "Delete customers",
  "users.view_user": "View staff users",
  "users.create_user": "Add staff users",
  "users.edit_user": "Edit staff users",
  "users.delete_user": "Deactivate staff users",
  "memberships.view_membership": "View memberships",
  "memberships.create_membership": "Create memberships",
  "memberships.edit_membership": "Edit memberships",
  "payments.view_payment": "View payments",
  "payments.record_payment": "Record payments",
  "attendance.view_attendance": "View attendance",
  "attendance.log_attendance": "Log attendance",
  "workouts.view_workout": "View workout plans",
  "workouts.create_workout": "Create workout plans",
  "workouts.edit_workout": "Edit workout plans",
  "diets.view_diet": "View diet plans",
  "diets.create_diet": "Create diet plans",
  "diets.edit_diet": "Edit diet plans",
  "exercises.view_exercise": "View exercises",
  "exercises.create_exercise": "Create exercises",
  "exercises.edit_exercise": "Edit exercises",
  "exercises.delete_exercise": "Delete exercises",
  "feedback.view_feedback": "View feedback",
  "feedback.create_feedback": "Submit feedback",
  "trainers.view_trainer": "View trainers",
  "trainers.edit_trainer": "Edit trainer assignments",
  "trainers.view_session": "View PT sessions",
  "trainers.edit_session": "Manage PT sessions",
  "inventory.view_equipment": "View equipment",
  "reviews.view_review": "View reviews",
  "tenants.view_tenant": "View gym settings",
  "tenants.edit_tenant": "Edit gym settings",
  "access.view_device": "View access devices",
  "marketplace.view_product": "Browse marketplace",
  "marketplace.edit_product": "Manage marketplace products",
  "marketplace.delete_product": "Remove marketplace products",
  "marketplace.view_cart": "View shopping carts",
  "marketplace.edit_cart": "Edit shopping carts",
  "marketplace.view_order": "View orders",
  "marketplace.create_order": "Place orders",
  "marketplace.edit_order": "Edit orders",
  "marketplace.delete_order": "Cancel orders",
};

/** Display name per permission domain (the app_label of a code). */
export const PERMISSION_GROUP_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  reports: "Reports",
  branches: "Branches",
  customers: "Customers",
  users: "Staff users",
  memberships: "Memberships",
  payments: "Payments",
  attendance: "Attendance",
  access: "Access devices",
  trainers: "Trainers & PT sessions",
  workouts: "Workout plans",
  exercises: "Exercises",
  diets: "Diet plans",
  inventory: "Inventory",
  marketplace: "Marketplace",
  reviews: "Reviews",
  feedback: "Feedback",
  tenants: "Gym settings",
};

/** Section order mirrors the sidebar — operations first, settings last. */
const GROUP_ORDER = [
  "dashboard",
  "branches",
  "customers",
  "users",
  "memberships",
  "payments",
  "attendance",
  "access",
  "trainers",
  "workouts",
  "exercises",
  "diets",
  "inventory",
  "marketplace",
  "reviews",
  "feedback",
  "reports",
  "tenants",
];

/** True when the permission list is the full-access wildcard. */
export function isFullAccess(permissions: string[]): boolean {
  return permissions.includes("*");
}

/** Readable label for a permission code; unknown codes are humanized. */
export function permissionLabel(code: string): string {
  const known = PERMISSION_LABELS[code];
  if (known) return known;
  const [appLabel, actionResource] = code.split(".");
  if (!appLabel || !actionResource) return code;
  const [action, ...resource] = actionResource.split("_");
  const verb = { view: "View", create: "Create", edit: "Edit", delete: "Delete" }[action] ?? action;
  return `${verb} ${resource.join(" ")}`.trim();
}

export interface PermissionGroup {
  /** Raw domain key (the app_label of the grouped codes). */
  key: string;
  /** Display name for the group. */
  label: string;
  /** Permission codes in the group, in the matrix's given order. */
  permissions: string[];
}

/**
 * Group permission codes by domain for display. The full-access wildcard is
 * not a domain — callers handle it via {@link isFullAccess}. Known domains
 * come first in sidebar order; unknown ones follow alphabetically so future
 * permissions still render sensibly.
 */
export function groupPermissions(permissions: string[]): PermissionGroup[] {
  const grouped = new Map<string, string[]>();
  for (const code of permissions) {
    if (code === "*") continue;
    const domain = code.split(".")[0] || "other";
    const bucket = grouped.get(domain);
    if (bucket) bucket.push(code);
    else grouped.set(domain, [code]);
  }
  const keys = [...grouped.keys()].sort((a, b) => {
    const ia = GROUP_ORDER.indexOf(a);
    const ib = GROUP_ORDER.indexOf(b);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return a.localeCompare(b);
  });
  return keys.map((key) => ({
    key,
    label: PERMISSION_GROUP_LABELS[key] ?? key.charAt(0).toUpperCase() + key.slice(1),
    permissions: grouped.get(key) ?? [],
  }));
}

/** The fixed role codes the Roles page presents, in display order. */
export const DISPLAYED_ROLES = [
  "gym_owner",
  "manager",
  "trainer",
  "dietitian",
  "customer",
] as const;

export type DisplayedRole = (typeof DISPLAYED_ROLES)[number];

/** Grouped, labeled permission sections for one role, ready to render. */
export function rolePermissionSections(role: DisplayedRole): PermissionGroup[] {
  return groupPermissions([...ROLE_PERMISSIONS[role] ?? []]);
}
