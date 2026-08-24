"use client";

import {
  LayoutDashboard,
  Target,
  Ruler,
  HeartPulse,
  Camera,
  CreditCard,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type CustomerTabKey =
  | "overview"
  | "goals"
  | "measurements"
  | "health"
  | "photos"
  | "payments";

interface TabDefinition {
  key: CustomerTabKey;
  label: string;
  icon: LucideIcon;
}

const TABS: TabDefinition[] = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "goals", label: "Fitness Goals", icon: Target },
  { key: "measurements", label: "Body Measurements", icon: Ruler },
  { key: "health", label: "Health Profile", icon: HeartPulse },
  { key: "photos", label: "Progress Photos", icon: Camera },
  { key: "payments", label: "Payment History", icon: CreditCard },
];

interface CustomerTabsProps {
  active: CustomerTabKey;
  onChange: (tab: CustomerTabKey) => void;
}

export function CustomerTabs({ active, onChange }: CustomerTabsProps) {
  return (
    <nav className="-mb-px flex gap-1 overflow-x-auto" aria-label="Customer tabs">
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={cn(
              "flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium transition-colors",
              isActive
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
            )}
            aria-current={isActive ? "page" : undefined}
          >
            <Icon className="h-4 w-4" />
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
