"use client";

import { ShieldCheck } from "lucide-react";
import { Badge, Card, CardBody } from "@/components/ui";
import { getRoleColor, getRoleLabel, ROLE_PERMISSIONS } from "@/lib/permissions";
import {
  DISPLAYED_ROLES,
  isFullAccess,
  permissionLabel,
  rolePermissionSections,
  type DisplayedRole,
} from "@/lib/permission-labels";

/** Owner-facing blurb per role — what the role is for, in plain language. */
const ROLE_DESCRIPTIONS: Record<DisplayedRole, string> = {
  gym_owner: "Full control of the gym — billing, staff, branches, and every module.",
  manager: "Runs day-to-day operations: customers, memberships, payments, attendance, and staff.",
  trainer: "Coaches members — workouts, exercises, attendance, and their PT sessions.",
  dietitian: "Builds and manages diet plans for members.",
  customer: "Members see their own membership, payments, attendance, and plans.",
};

/**
 * #92: Roles & permissions — what each role in the gym can do, presented as
 * readable labels grouped by product area. A static view over the frontend
 * RBAC matrix (`lib/permissions.ts`); permission codes never render raw.
 */
export function RolesPermissions() {
  return (
    <div className="space-y-4" data-testid="roles-permissions">
      <p className="text-sm text-gray-500">
        What each role in your gym can do. Roles are fixed — contact support to
        change someone&apos;s access.
      </p>

      {DISPLAYED_ROLES.map((role) => {
        const codes = [...(ROLE_PERMISSIONS[role] ?? [])];
        const sections = rolePermissionSections(role);
        const fullAccess = isFullAccess(codes);
        const total = sections.reduce((n, s) => n + s.permissions.length, 0);
        return (
          <Card key={role} data-testid={`role-card-${role}`}>
            <CardBody className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge className={getRoleColor(role)} data-testid={`role-badge-${role}`}>
                  {getRoleLabel(role)}
                </Badge>
                <p className="text-sm text-gray-500">{ROLE_DESCRIPTIONS[role]}</p>
                <span
                  className="ml-auto inline-flex items-center gap-1.5 text-xs text-gray-400"
                  data-testid={`role-summary-${role}`}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {fullAccess
                    ? "Full access"
                    : `${total} permission${total === 1 ? "" : "s"} across ${sections.length} ${sections.length === 1 ? "area" : "areas"}`}
                </span>
              </div>

              {fullAccess ? (
                <p className="rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-800" data-testid={`role-full-access-${role}`}>
                  Can do everything in the dashboard, including owner-only settings.
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {sections.map((section) => (
                    <div key={section.key} data-testid={`role-section-${role}-${section.key}`}>
                      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
                        {section.label}
                      </h3>
                      <ul className="flex flex-wrap gap-1.5">
                        {section.permissions.map((code) => (
                          <li
                            key={code}
                            className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700"
                          >
                            {permissionLabel(code)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        );
      })}
    </div>
  );
}
