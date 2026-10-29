import {
  DISPLAYED_ROLES,
  PERMISSION_LABELS,
  groupPermissions,
  isFullAccess,
  permissionLabel,
  rolePermissionSections,
} from "@/lib/permission-labels";
import { ROLE_PERMISSIONS } from "@/lib/permissions";

describe("permission labels (issue #92)", () => {
  it("has a hand-written label for every code in the frontend matrix", () => {
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const code of perms) {
        if (code === "*") continue;
        expect(PERMISSION_LABELS[code]).toBeDefined();
      }
    }
  });

  it("never labels a code with the raw code itself", () => {
    for (const [code, label] of Object.entries(PERMISSION_LABELS)) {
      expect(label).not.toEqual(code);
      expect(label).not.toMatch(/[._]/); // no dots or snake_case leaking through
    }
  });

  it("humanizes unknown codes instead of showing them raw", () => {
    expect(permissionLabel("loans.create_loan")).toBe("Create loan");
    expect(permissionLabel("access.view_device")).toBe("View access devices");
  });

  it("falls back to the raw string for malformed codes", () => {
    expect(permissionLabel("weird")).toBe("weird");
  });
});

describe("groupPermissions (issue #92)", () => {
  it("groups codes by domain and orders them operations-first", () => {
    const groups = groupPermissions([
      "payments.view_payment",
      "customers.view_customer",
      "dashboard.view_dashboard",
    ]);
    expect(groups.map((g) => g.key)).toEqual(["dashboard", "customers", "payments"]);
    expect(groups[1]).toEqual({
      key: "customers",
      label: "Customers",
      permissions: ["customers.view_customer"],
    });
  });

  it("skips the full-access wildcard — callers handle it via isFullAccess", () => {
    expect(groupPermissions(["*"])).toEqual([]);
    expect(isFullAccess(["*"])).toBe(true);
    expect(isFullAccess(["customers.view_customer"])).toBe(false);
  });

  it("appends unknown domains after the known order, alphabetically", () => {
    const groups = groupPermissions([
      "loans.create_loan",
      "tenants.edit_tenant",
      "zebras.view_zebra",
    ]);
    expect(groups.map((g) => g.key)).toEqual(["tenants", "loans", "zebras"]);
    expect(groups[1].label).toBe("Loans"); // title-cased fallback label
  });

  it("keeps the matrix's given order inside a group", () => {
    const groups = groupPermissions([
      "customers.edit_customer",
      "customers.view_customer",
      "customers.create_customer",
    ]);
    expect(groups[0].permissions).toEqual([
      "customers.edit_customer",
      "customers.view_customer",
      "customers.create_customer",
    ]);
  });
});

describe("rolePermissionSections (issue #92)", () => {
  it("returns labeled sections for every displayed role", () => {
    expect(DISPLAYED_ROLES).toEqual([
      "gym_owner",
      "manager",
      "trainer",
      "dietitian",
      "customer",
    ]);
    for (const role of DISPLAYED_ROLES) {
      const sections = rolePermissionSections(role);
      if (isFullAccess([...ROLE_PERMISSIONS[role]])) {
        expect(sections).toEqual([]); // wildcard roles render "Full access" instead
      } else {
        expect(sections.length).toBeGreaterThan(0);
        for (const section of sections) {
          expect(section.permissions.length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("labels every section item for the manager role", () => {
    for (const section of rolePermissionSections("manager")) {
      for (const code of section.permissions) {
        expect(PERMISSION_LABELS[code]).toBeDefined();
      }
    }
  });
});
