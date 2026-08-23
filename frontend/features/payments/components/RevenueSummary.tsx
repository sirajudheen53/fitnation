"use client";

import { CalendarDays, CalendarRange, CalendarClock } from "lucide-react";
import { Card, CardBody } from "@/components/ui";
import type { RevenueSummary as RevenueSummaryData } from "@/types/payment";

interface RevenueSummaryProps {
  summary: RevenueSummaryData;
  loading?: boolean;
}

export function formatCurrency(value: number | string): string {
  const num = Number(value) || 0;
  return `₹${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function RevenueSummary({ summary, loading = false }: RevenueSummaryProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Card key={i}>
            <CardBody>
              <div className="h-16 animate-pulse rounded-lg bg-gray-100" />
            </CardBody>
          </Card>
        ))}
      </div>
    );
  }

  const items = [
    {
      label: "Today",
      value: summary.today,
      icon: CalendarDays,
      accent: "text-brand-600",
    },
    {
      label: "This week",
      value: summary.this_week,
      icon: CalendarRange,
      accent: "text-green-600",
    },
    {
      label: "This month",
      value: summary.this_month,
      icon: CalendarClock,
      accent: "text-indigo-600",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <Card key={item.label}>
            <CardBody>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">{item.label}</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">
                    {formatCurrency(item.value)}
                  </p>
                </div>
                <div className={`rounded-lg bg-gray-50 p-3 ${item.accent}`}>
                  <Icon className="h-6 w-6" />
                </div>
              </div>
            </CardBody>
          </Card>
        );
      })}
    </div>
  );
}
