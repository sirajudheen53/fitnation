"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Archive, KeyRound, Pause, Pencil, Play, Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Button, Card, CardBody, Spinner } from "@/components/ui";
import {
  errorMessage,
  fetchAdminTenants,
  updateAdminTenant,
} from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import { ArchiveGymDialog } from "@/features/admin/components/ArchiveGymDialog";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { EditGymDialog } from "@/features/admin/components/EditGymDialog";
import { RotateCredentialsDialog } from "@/features/admin/components/RotateCredentialsDialog";
import type { AdminTenant } from "@/types/admin";

const STATUS_VARIANTS: Record<string, "success" | "danger" | "warning" | "default"> = {
  active: "success",
  suspended: "danger",
  trial: "warning",
  cancelled: "default",
  archived: "default",
};

export default function AdminGymsPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));
  const [editTarget, setEditTarget] = useState<AdminTenant | null>(null);
  const [rotateTarget, setRotateTarget] = useState<AdminTenant | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<AdminTenant | null>(null);
  const [suspendTarget, setSuspendTarget] = useState<AdminTenant | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (user && user.role !== "platform_admin") {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/admin");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        setTenants(await fetchAdminTenants(authToken));
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [router, user]);

  function replaceTenant(updated: AdminTenant) {
    setTenants((list) => list.map((t) => (t.id === updated.id ? updated : t)));
  }

  async function setTenantStatus(tenant: AdminTenant, status: "active" | "suspended") {
    const token = getToken();
    if (!token) return;
    setBusyId(tenant.id);
    try {
      const updated = await updateAdminTenant(tenant.id, { status }, token);
      replaceTenant(updated);
      toast.success(
        status === "suspended"
          ? `${updated.name} suspended`
          : `${updated.name} reactivated`,
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <DashboardLayout
      title="Gyms — Platform Admin"
      actions={
        <Button onClick={() => router.push("/admin/onboard")}>
          <Plus className="mr-2 h-4 w-4" /> Onboard Gym
        </Button>
      }
    >
      {error && (
        <Card className="mb-4">
          <CardBody className="text-sm text-red-600">{error}</CardBody>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : tenants.length === 0 ? (
        <Card>
          <CardBody className="py-12 text-center text-sm text-gray-500">
            No gyms onboarded yet. Use “Onboard Gym” to add the first one.
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Gym</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Plan</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Members</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Branches</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Onboarded</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tenants.map((t) => {
                    const archived = t.status === "archived";
                    const busy = busyId === t.id;
                    return (
                      <tr key={t.id} className={archived ? "bg-gray-50/60" : "hover:bg-gray-50"}>
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-900">{t.name}</div>
                          <div className="text-xs text-gray-500">{t.contact_email}</div>
                        </td>
                        <td className="px-4 py-3 capitalize text-gray-700">
                          {t.subscription_plan}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={STATUS_VARIANTS[t.status] ?? "default"}>
                            {t.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 font-mono text-gray-900">{t.member_count}</td>
                        <td className="px-4 py-3 font-mono text-gray-600">{t.branch_count}</td>
                        <td className="px-4 py-3 text-xs text-gray-500">
                          {new Date(t.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={archived || busy}
                              title={archived ? "Archived gyms are read-only" : "Edit gym"}
                              aria-label={`Edit ${t.name}`}
                              onClick={() => setEditTarget(t)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={archived || busy}
                              title={
                                archived
                                  ? "Archived gyms are read-only"
                                  : "Rotate owner credentials"
                              }
                              aria-label={`Rotate credentials for ${t.name}`}
                              onClick={() => setRotateTarget(t)}
                            >
                              <KeyRound className="h-4 w-4" />
                            </Button>
                            {t.status === "suspended" ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={archived || busy}
                                className="text-green-600 hover:bg-green-50"
                                title="Reactivate gym"
                                aria-label={`Reactivate ${t.name}`}
                                onClick={() => void setTenantStatus(t, "active")}
                              >
                                <Play className="h-4 w-4" />
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={archived || busy}
                                className="text-amber-600 hover:bg-amber-50"
                                title="Suspend gym"
                                aria-label={`Suspend ${t.name}`}
                                onClick={() => setSuspendTarget(t)}
                              >
                                <Pause className="h-4 w-4" />
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={archived || busy}
                              className="text-red-600 hover:bg-red-50"
                              title={archived ? "Gym is archived" : "Archive gym"}
                              aria-label={`Archive ${t.name}`}
                              onClick={() => setArchiveTarget(t)}
                            >
                              <Archive className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      {editTarget && (
        <EditGymDialog
          tenant={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={(updated) => {
            setEditTarget(null);
            replaceTenant(updated);
            toast.success(`${updated.name} updated`);
          }}
        />
      )}

      {rotateTarget && (
        <RotateCredentialsDialog
          tenant={rotateTarget}
          onClose={() => setRotateTarget(null)}
        />
      )}

      {suspendTarget && (
        <ConfirmDialog
          title={`Suspend ${suspendTarget.name}?`}
          confirmLabel="Suspend Gym"
          destructive
          onConfirm={() => {
            const target = suspendTarget;
            setSuspendTarget(null);
            void setTenantStatus(target, "suspended");
          }}
          onClose={() => setSuspendTarget(null)}
        >
          <p>
            The owner will not be able to log in, and all API access for this
            gym is blocked until you reactivate it.
          </p>
        </ConfirmDialog>
      )}

      {archiveTarget && (
        <ArchiveGymDialog
          tenant={archiveTarget}
          onClose={() => setArchiveTarget(null)}
          onArchived={(updated) => {
            setArchiveTarget(null);
            replaceTenant(updated);
            toast.success(`${updated.name} archived`);
          }}
        />
      )}
    </DashboardLayout>
  );
}
