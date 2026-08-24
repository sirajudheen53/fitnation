"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  BranchInfo,
  BranchStatsGrid,
  emptyBranchStats,
} from "@/features/branches/components/BranchDetail";
import { Card, CardHeader, CardBody, Spinner, Alert, Button } from "@/components/ui";
import { fetchBranch, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Branch, BranchStats } from "@/types/branch";

export default function BranchDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [branch, setBranch] = useState<Branch | null>(null);
  const [stats, setStats] = useState<BranchStats>(emptyBranchStats());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/branches");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchBranch(id, authToken);
        setBranch(data);
        // Branch stats endpoint is not yet exposed by the backend — derive locally
        // from the branch metadata if present, otherwise show zeroed stats.
        const metaStats = data.metadata?.stats as Partial<BranchStats> | undefined;
        setStats({
          total_customers: metaStats?.total_customers ?? 0,
          active_memberships: metaStats?.active_memberships ?? 0,
          assigned_trainers: metaStats?.assigned_trainers ?? 0,
          todays_attendance: metaStats?.todays_attendance ?? 0,
        });
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  return (
    <DashboardLayout
      title="Branch details"
      actions={
        branch ? (
          <Link href={`/branches/${branch.id}/edit`}>
            <Button size="sm" variant="outline">
              <Pencil className="h-4 w-4" /> Edit
            </Button>
          </Link>
        ) : null
      }
    >
      <div className="mb-4">
        <Link
          href="/branches"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to branches
        </Link>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && !branch && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && branch && (
        <div className="space-y-6">
          <BranchStatsGrid stats={stats} />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="text-lg font-semibold text-gray-900">Branch information</h3>
              </CardHeader>
              <CardBody>
                <BranchInfo branch={branch} />
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="text-lg font-semibold text-gray-900">Quick links</h3>
              </CardHeader>
              <CardBody>
                <div className="flex flex-col gap-3">
                  <Link
                    href={`/branches/${branch.id}/edit`}
                    className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    <Pencil className="h-4 w-4 text-brand-600" /> Edit branch details
                  </Link>
                  <p className="text-xs text-gray-500">
                    Manage trainers and view customer rosters for this branch from the
                    Customers and Trainers sections.
                  </p>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
