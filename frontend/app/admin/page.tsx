"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Button, Card, CardBody, Spinner } from "@/components/ui";
import { errorMessage, fetchAdminTenants } from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import type { AdminTenant } from "@/types/admin";

const STATUS_VARIANTS: Record<string, "success" | "danger" | "warning" | "default"> = {
  active: "success",
  suspended: "danger",
  trial: "warning",
  cancelled: "default",
};

export default function AdminGymsPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));

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
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tenants.map((t) => (
                    <tr key={t.id} className="hover:bg-gray-50">
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </DashboardLayout>
  );
}