"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Send, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CustomerTable } from "@/features/customers/components/CustomerTable";
import { getCustomerDisplayName } from "@/features/customers/components/CustomerAvatar";
import { deriveAppAccessDisplay, type AppAccessDisplay } from "@/features/customers/lib/appAccess";
import { invitableIds, sendBulkInvites } from "@/features/customers/lib/bulkInvite";
import { Button, Alert, Spinner } from "@/components/ui";
import {
  fetchCustomers,
  fetchMembershipPlans,
  fetchMemberships,
  sendAppInvite,
  deleteCustomer,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Customer } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";

type AppAccessFilter = "all" | "entitled" | "grace" | "not_entitled";

const FILTER_OPTIONS: { value: AppAccessFilter; label: string }[] = [
  { value: "all", label: "All members" },
  { value: "entitled", label: "App: entitled" },
  { value: "grace", label: "App: read-only grace" },
  { value: "not_entitled", label: "App: not entitled" },
];

function matchesFilter(display: AppAccessDisplay | undefined, filter: AppAccessFilter): boolean {
  if (filter === "all") return true;
  if (!display) return false;
  if (filter === "entitled") return display.status === "active";
  if (filter === "grace") return display.status === "grace";
  return display.status === "expired" || display.status === "none";
}

export default function CustomersPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [filter, setFilter] = useState<AppAccessFilter>("all");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [inviting, setInviting] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/customers")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/customers");
      return;
    }

    const authToken: string = token;

    async function load() {
      try {
        const response = await fetchCustomers(authToken);
        setCustomers(response.results);
        // App-access derivation needs memberships + plans (both existing
        // endpoints); best-effort — the column shows "—" when this fails.
        try {
          const [membershipRes, planRes] = await Promise.all([
            fetchMemberships(authToken),
            fetchMembershipPlans(authToken),
          ]);
          setMemberships(membershipRes.results);
          setPlans(planRes.results);
        } catch {
          /* app-access column degrades to "—" */
        }
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/customers/new") : false;
  const canOnboard = userRole ? canAccessRoute(userRole, "/onboarding/member") : false;
  const canInvite = userRole ? canAccessRoute(userRole, "/customers") : false;

  const today = useMemo(() => {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
  }, []);

  /** customer_id → derived app-access display (list columns + filter). */
  const appAccessByCustomer = useMemo(() => {
    const byCustomer: Record<number, Membership[]> = {};
    for (const membership of memberships) {
      (byCustomer[membership.customer_id] ??= []).push(membership);
    }
    const map: Record<number, AppAccessDisplay> = {};
    for (const customer of customers) {
      map[customer.id] = deriveAppAccessDisplay(
        customer,
        byCustomer[customer.id] ?? null,
        plans,
        today,
      );
    }
    return map;
  }, [customers, memberships, plans, today]);

  const visibleCustomers = useMemo(
    () => customers.filter((c) => matchesFilter(appAccessByCustomer[c.id], filter)),
    [customers, appAccessByCustomer, filter],
  );

  /**
   * Bulk-invite targets: selected members who are entitled (active or grace)
   * but whose last invite isn't a successful send (FBOS-011 F5).
   */
  const eligibleIds = useMemo(
    () => invitableIds(selectedIds, appAccessByCustomer, customers),
    [selectedIds, appAccessByCustomer, customers],
  );

  const handleBulkInvite = async () => {
    const token = getToken();
    if (!token || eligibleIds.length === 0) return;
    setInviting(true);
    try {
      // NOTE: no batch endpoint in the backend contract yet — one call per
      // member against POST /memberships/app-invite/ (24 h dedupe makes this
      // safe). A batch endpoint would remove the N requests.
      const outcome = await sendBulkInvites(eligibleIds, (id) =>
        sendAppInvite(id, token, false),
      );
      if (outcome.sent > 0) toast.success(`Invites sent: ${outcome.sent}`);
      if (outcome.already_sent > 0) toast.info(`Already invited recently: ${outcome.already_sent}`);
      if (outcome.failed > 0) toast.error(`Failed: ${outcome.failed}`);
      setSelectedIds([]);
    } finally {
      setInviting(false);
    }
  };

  const handleDelete = async (customer: Customer) => {
    if (!confirm(`Delete customer "${getCustomerDisplayName(customer)}"?`)) return;
    const token = getToken();
    if (!token) return;
    setDeleting(customer.id);
    try {
      await deleteCustomer(customer.id, token);
      setCustomers((prev) => prev.filter((c) => c.id !== customer.id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <DashboardLayout
      title="Customers"
      actions={
        <div className="flex items-center gap-2">
          {canCreate && (
            <Link href="/customers/new">
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4" /> Blank form
              </Button>
            </Link>
          )}
          {canOnboard && (
            <Link href="/onboarding/member">
              <Button size="sm" data-testid="new-member-cta">
                <UserPlus className="h-4 w-4" /> New member
              </Button>
            </Link>
          )}
        </div>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}

      {!loading && customers.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label htmlFor="app-access-filter" className="text-sm font-medium text-gray-700">
            App access
          </label>
          <select
            id="app-access-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value as AppAccessFilter)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {FILTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          {canInvite && selectedIds.length > 0 && (
            <div className="ml-auto flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2">
              <span className="text-sm text-gray-700">
                {selectedIds.length} selected
                {eligibleIds.length < selectedIds.length && (
                  <span className="text-gray-500"> · {eligibleIds.length} invitable</span>
                )}
              </span>
              <Button
                size="sm"
                loading={inviting}
                disabled={eligibleIds.length === 0}
                onClick={handleBulkInvite}
                data-testid="bulk-invite"
              >
                <Send className="h-4 w-4" />
                Send app invite
              </Button>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <CustomerTable
          customers={visibleCustomers}
          onDelete={handleDelete}
          loading={deleting !== null}
          appAccessByCustomer={appAccessByCustomer}
          onSelectionChange={setSelectedIds}
        />
      )}
      {deleting !== null && (
        <div className="sr-only" role="status" aria-live="polite">
          Deleting customer…
        </div>
      )}
    </DashboardLayout>
  );
}
