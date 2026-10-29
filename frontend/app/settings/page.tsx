"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CreditCard, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardBody } from "@/components/ui";
import { GymCodeCard } from "@/features/settings/components/GymCodeCard";
import { ModulesCard } from "@/features/settings/components/ModulesCard";
import { WhatsAppChannels } from "@/features/settings/components/WhatsAppChannels";
import { getStoredUser } from "@/lib/auth";

/** Settings index — the sidebar "Settings" entry lands here. */
export default function SettingsPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const user = getStoredUser();
    if (!user) {
      router.replace("/login?next=/settings");
      return;
    }
    if (user.role !== "gym_owner" && user.role !== "platform_admin") {
      router.replace("/unauthorized");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration from localStorage before auth redirect
    setReady(true);
  }, [router]);

  const settingLinks = [
    {
      href: "/settings/razorpay",
      title: "Razorpay",
      description: "Accept online payments for memberships and services.",
      icon: CreditCard,
    },
    {
      href: "/settings/roles",
      title: "Roles & permissions",
      description: "See what each role in your gym can do, in plain language.",
      icon: ShieldCheck,
    },
  ];

  return (
    <DashboardLayout title="Settings">
      {ready ? (
        <div className="max-w-3xl space-y-4">
          <GymCodeCard />
          <ModulesCard />
          {/* Channel-aware WhatsApp cards (issue #67/#73): WATI + Gupshup with
              live configured state — whichever is configured carries messages. */}
          <WhatsAppChannels />
          <section className="pt-2">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {settingLinks.map((item) => (
                <Link key={item.href} href={item.href} className="group">
                  <Card className="h-full transition-colors group-hover:border-brand-400">
                    <CardBody className="space-y-2">
                      <item.icon className="h-6 w-6 text-brand-600" />
                      <h2 className="font-semibold text-gray-900">{item.title}</h2>
                      <p className="text-sm text-gray-500">{item.description}</p>
                    </CardBody>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        </div>
      ) : (
        <div className="flex h-48 items-center justify-center text-sm text-gray-500">
          Checking permissions…
        </div>
      )}
    </DashboardLayout>
  );
}
