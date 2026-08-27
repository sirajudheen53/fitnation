"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CreditCard } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert } from "@/components/ui";
import { getStoredUser } from "@/lib/auth";
import { RazorpayConfigForm } from "@/features/razorpay/components/RazorpayConfigForm";

export default function RazorpaySettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getStoredUser>>(null);

  useEffect(() => {
    const u = getStoredUser();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration from localStorage before auth redirect
    setUser(u);
    if (!u) {
      router.replace("/login?next=/settings/razorpay");
      return;
    }
    // Only owners / platform admins may configure payment integrations.
    if (u.role !== "gym_owner" && u.role !== "platform_admin") {
      router.replace("/unauthorized");
    }
  }, [router]);

  return (
    <DashboardLayout
      title="Razorpay settings"
      actions={
        <span className="inline-flex items-center gap-2 text-sm text-gray-500">
          <CreditCard className="h-4 w-4" />
          Payment gateway
        </span>
      }
    >
      {user?.role === "gym_owner" || user?.role === "platform_admin" ? (
        <div className="max-w-3xl">
          <RazorpayConfigForm />
        </div>
      ) : (
        <Alert variant="info">Checking permissions…</Alert>
      )}
    </DashboardLayout>
  );
}
