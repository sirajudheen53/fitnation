"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Card, CardHeader, CardBody } from "@/components/ui";
import type { RevenueResponse } from "@/types/dashboard";

type Period = "daily" | "weekly" | "monthly";

interface RevenueChartProps {
  data: RevenueResponse;
  loading?: boolean;
}

export function RevenueChart({ data, loading = false }: RevenueChartProps) {
  const [period, setPeriod] = useState<Period>("daily");

  const chartData = (data?.[period] ?? []).map((point) => ({
    label: point.label,
    revenue: point.amount,
  }));

  if (loading) {
    return (
      <Card>
        <CardBody>
          <div className="h-64 animate-pulse rounded-lg bg-gray-100" />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Revenue</h2>
          <div className="flex gap-1 rounded-lg bg-gray-100 p-1">
            {(["daily", "weekly", "monthly"] as Period[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors ${
                  period === p
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <p className="text-sm text-gray-500">No revenue data available.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip formatter={(v) => [`₹${Number(v).toLocaleString()}`, "Revenue"]} />
                <Bar dataKey="revenue" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
