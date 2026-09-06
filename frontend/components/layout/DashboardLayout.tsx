"use client";

import { type ReactNode, useState } from "react";
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
  ShoppingBag,
  MessageCircle,
  Utensils,
  TrendingUp,
  BarChart3,
  Bell,
  Settings,
  LogOut,
  Menu,
  X,
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
  { href: "/trainers/performance", label: "Trainer Performance", icon: TrendingUp },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/workouts", label: "Workouts", icon: Dumbbell },
  { href: "/diet", label: "Diets", icon: Apple },
  { href: "/marketplace", label: "Marketplace", icon: ShoppingBag },
  { href: "/ai-coach", label: "AI Coach", icon: MessageCircle },
  { href: "/notifications/settings", label: "Notifications", icon: Bell },
  { href: "/nutrition", label: "Nutrition", icon: Utensils },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function DashboardLayout({ children, title, actions }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const user = typeof window !== "undefined" ? getStoredUser() : null;
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  const renderNav = (onNavigate?: () => void) => (
    <>
      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
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
          onClick={() => {
            onNavigate?.();
            handleLogout();
          }}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar (lg+) */}
      <aside className="sticky top-0 hidden h-screen w-64 flex-col border-r border-gray-200 bg-white lg:flex">
        <div className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Dumbbell className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold text-gray-900">FitNation</span>
        </div>
        {renderNav()}
      </aside>

      {/* Mobile drawer (<lg) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-gray-900/50"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-gray-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
                  <Dumbbell className="h-5 w-5" />
                </div>
                <span className="text-lg font-bold text-gray-900">FitNation</span>
              </div>
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-900"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {renderNav(() => setMobileOpen(false))}
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex-1">
        <header className="sticky top-0 z-10 border-b border-gray-200 bg-white px-4 py-4 sm:px-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setMobileOpen(true)}
                aria-label="Open menu"
                className="rounded-lg p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900 lg:hidden"
              >
                <Menu className="h-6 w-6" />
              </button>
              <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        </header>
        <main className="p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}