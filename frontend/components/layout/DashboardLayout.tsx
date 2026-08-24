"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  Users,
  CreditCard,
  Wallet,
  CalendarCheck,
  Dumbbell,
  Apple,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logout, getStoredUser } from "@/lib/auth";

interface DashboardLayoutProps {
  children: ReactNode;
  title: string;
  actions?: ReactNode;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/branches", label: "Branches", icon: Building2 },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/memberships", label: "Memberships", icon: CreditCard },
  { href: "/payments", label: "Payments", icon: Wallet },
  { href: "/attendance", label: "Attendance", icon: CalendarCheck },
  { href: "/workouts", label: "Workouts", icon: Dumbbell },
  { href: "/diet", label: "Diets", icon: Apple },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function DashboardLayout({ children, title, actions }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const user = typeof window !== "undefined" ? getStoredUser() : null;

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 flex-col border-r border-gray-200 bg-white lg:flex">
        <div className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Dumbbell className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold text-gray-900">FitNation</span>
        </div>

        <nav className="flex-1 space-y-1 px-4 py-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-gray-700 hover:bg-gray-50 hover:text-gray-900",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-gray-100 p-4">
          <div className="mb-2 text-xs text-gray-500">{user?.email || "—"}</div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1">
        <header className="sticky top-0 z-10 border-b border-gray-200 bg-white px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        </header>
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
