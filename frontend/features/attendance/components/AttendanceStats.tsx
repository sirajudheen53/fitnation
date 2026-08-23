"use client";

import { CalendarCheck, Clock, TrendingDown } from "lucide-react";
import { Card, CardBody } from "@/components/ui";
import type { AttendanceStats as AttendanceStatsData } from "@/types/attendance";

interface AttendanceStatsProps {
  stats: AttendanceStatsData;
  loading?: boolean;
}

export function AttendanceStats({ stats, loading = false }: AttendanceStatsProps) {
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
      label: "Today's check-ins",
      value: String(stats.today_count),
      icon: CalendarCheck,
      accent: "text-brand-600",
    },
    {
      label: "Peak hour",
      value: stats.peak_hour ? `${stats.peak_hour} (${stats.peak_hour_count})` : "—",
      icon: Clock,
      accent: "text-amber-600",
    },
    {
      label: "Dropout hour",
      value: stats.most_frequent_dropout_hour ?? "—",
      icon: TrendingDown,
      accent: "text-red-600",
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
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{item.value}</p>
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
