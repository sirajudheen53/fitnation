"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UserPlus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { OnboardingWizard } from "@/features/onboarding/components/OnboardingWizard";
import { getStoredUser } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";

/**
 * New Member Onboarding — the 90-second front-desk wizard (FBOS-011 F2,
 * onboarding-design). Route note: `/onboarding` is the vendor signup wizard,
 * so the member wizard lives at `/onboarding/member` (FBOS-011 correction #2).
 */
export default function MemberOnboardingPage() {
  const router = useRouter();
  // null = still checking auth/permission; otherwise the wizard mounts.
  const [boot, setBoot] = useState<{ ready: boolean; branchId: number | null }>({
    ready: false,
    branchId: null,
  });

  useEffect(() => {
    const user = getStoredUser();
    if (!user) {
      router.replace("/login?next=/onboarding/member");
      return;
    }
    if (!canAccessRoute(user.role, "/onboarding/member")) {
      router.replace("/unauthorized");
      return;
    }
    // Optional ?branch=2 deep link (read here to keep the page prerender-safe).
    const branchParam = new URLSearchParams(window.location.search).get("branch");
    const branchId = Number(branchParam);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration from localStorage before auth redirect
    setBoot({
      ready: true,
      branchId: Number.isInteger(branchId) && branchId > 0 ? branchId : null,
    });
  }, [router]);

  return (
    <DashboardLayout
      title="New member onboarding"
      actions={
        <span className="inline-flex items-center gap-2 text-sm text-gray-500">
          <UserPlus className="h-4 w-4" />
          ~90 seconds
        </span>
      }
    >
      {boot.ready ? (
        <OnboardingWizard initialBranchId={boot.branchId} />
      ) : (
        <div className="flex h-48 items-center justify-center text-sm text-gray-500">
          Checking permissions…
        </div>
      )}
    </DashboardLayout>
  );
}
