"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CreditCard, MessageCircle } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardBody } from "@/components/ui";
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

  const items = [
    {
      href: "/settings/whatsapp",
      title: "WhatsApp (WATI)",
      description:
        "Configure the gym's WhatsApp connection for app invites and OTPs, and send a test message.",
      icon: MessageCircle,
    },
    {
      href: "/settings/razorpay",
      title: "Razorpay",
      description: "Accept online payments for memberships and services.",
      icon: CreditCard,
    },
  ];

  return (
    <DashboardLayout title="Settings">
      {ready ? (
        <div className="grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
          {items.map((item) => (
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
      ) : (
        <div className="flex h-48 items-center justify-center text-sm text-gray-500">
          Checking permissions…
        </div>
      )}
    </DashboardLayout>
  );
}
