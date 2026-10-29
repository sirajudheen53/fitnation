"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert } from "@/components/ui";
import { getStoredUser } from "@/lib/auth";
import { RolesPermissions } from "@/features/settings/components/RolesPermissions";

/** #92: Roles & permissions — owner-only view of what each role can do. */
export default function RolesSettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getStoredUser>>(null);

  useEffect(() => {
    const u = getStoredUser();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration from localStorage before auth redirect
    setUser(u);
    if (!u) {
      router.replace("/login?next=/settings/roles");
      return;
    }
    // Owner-only surface — mirrors the other settings sub-pages.
    if (u.role !== "gym_owner" && u.role !== "platform_admin") {
      router.replace("/unauthorized");
    }
  }, [router]);

  return (
    <DashboardLayout
      title="Roles & permissions"
      actions={
        <span className="inline-flex items-center gap-2 text-sm text-gray-500">
          <ShieldCheck className="h-4 w-4" />
          Settings
        </span>
      }
    >
      {user?.role === "gym_owner" || user?.role === "platform_admin" ? (
        <div className="max-w-4xl">
          <RolesPermissions />
        </div>
      ) : (
        <Alert variant="info">Checking permissions…</Alert>
      )}
    </DashboardLayout>
  );
}
