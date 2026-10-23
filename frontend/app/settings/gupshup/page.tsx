"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert } from "@/components/ui";
import { getStoredUser } from "@/lib/auth";
import { GupshupConfigForm } from "@/features/settings/components/GupshupConfigForm";

export default function GupshupSettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getStoredUser>>(null);

  useEffect(() => {
    const u = getStoredUser();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration from localStorage before auth redirect
    setUser(u);
    if (!u) {
      router.replace("/login?next=/settings/gupshup");
      return;
    }
    // Owner-only surface (tenants.edit_tenant) — mirrors WhatsApp settings.
    if (u.role !== "gym_owner" && u.role !== "platform_admin") {
      router.replace("/unauthorized");
    }
  }, [router]);

  return (
    <DashboardLayout
      title="Gupshup WhatsApp settings"
      actions={
        <span className="inline-flex items-center gap-2 text-sm text-gray-500">
          <MessageCircle className="h-4 w-4" />
          Notifications
        </span>
      }
    >
      {user?.role === "gym_owner" || user?.role === "platform_admin" ? (
        <div className="max-w-3xl">
          <GupshupConfigForm />
        </div>
      ) : (
        <Alert variant="info">Checking permissions…</Alert>
      )}
    </DashboardLayout>
  );
}
