"use client";

import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardBody } from "@/components/ui";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: number;
  trendLabel?: string;
  accent?: string;
}

export function MetricCard({
  title,
  value,
  icon: Icon,
  trend,
  trendLabel = "vs last period",
  accent = "text-brand-600",
}: MetricCardProps) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">{title}</p>
          <div className={`rounded-lg bg-gray-50 p-2 ${accent}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <p className="mt-2 text-3xl font-semibold text-gray-900">{value}</p>
        {trend !== undefined && (
          <div className="mt-2 flex items-center gap-1 text-xs">
            {trend >= 0 ? (
              <TrendingUp className="h-3.5 w-3.5 text-green-600" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5 text-red-600" />
            )}
            <span className={trend >= 0 ? "text-green-600" : "text-red-600"}>
              {Math.abs(trend).toFixed(1)}%
            </span>
            <span className="text-gray-400">{trendLabel}</span>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
