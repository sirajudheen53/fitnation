"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { BranchTable } from "@/features/branches/components/BranchTable";
import { Button, Alert, Spinner, Input } from "@/components/ui";
import {
  fetchBranches,
  deleteBranch,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Branch } from "@/types/branch";

export default function BranchesPage() {
  const router = useRouter();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/branches")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/branches");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchBranches(authToken);
        setBranches(Array.isArray(res) ? res : []);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const filtered = branches.filter((b) => {
    const matchesSearch =
      !search ||
      b.name.toLowerCase().includes(search.toLowerCase()) ||
      `${b.address_line1} ${b.city}`.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && b.is_active) ||
      (statusFilter === "inactive" && !b.is_active);
    return matchesSearch && matchesStatus;
  });

  const handleDelete = async (branch: Branch) => {
    if (!window.confirm(`Delete branch "${branch.name}"? This cannot be undone.`)) return;
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    try {
      await deleteBranch(branch.id, authToken);
      setBranches((prev) => prev.filter((b) => b.id !== branch.id));
      toast.success("Branch deleted");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const canCreate = userRole ? canAccessRoute(userRole, "/branches") : false;

  return (
    <DashboardLayout
      title="Branches"
      actions={
        canCreate ? (
          <Link href="/branches/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> Add branch
            </Button>
          </Link>
        ) : null
      }
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <Input
            placeholder="Search by name or address"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            aria-label="Search branches"
          />
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="status-filter" className="sr-only">
            Filter by status
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && branches.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No branches yet. Add your first branch to get started.</p>
        </div>
      )}
      {!loading && branches.length > 0 && filtered.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No branches match your search.</p>
        </div>
      )}
      {!loading && filtered.length > 0 && (
        <BranchTable branches={filtered} onDelete={handleDelete} />
      )}
    </DashboardLayout>
  );
}
