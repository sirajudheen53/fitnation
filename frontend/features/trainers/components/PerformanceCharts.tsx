"use client";

import {
  Line,
  LineChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { Card, CardHeader, CardBody } from "@/components/ui";
import type { TrainerPerformanceRecord } from "@/types/trainer-performance";

/** Sort monthly records ascending by month and return chart-shaped points. */
export function monthlySeries(
  records: TrainerPerformanceRecord[],
): { month: string; revenue: number; rating: number | null; plans: number }[] {
  return [...records]
    .sort((a, b) => a.month.localeCompare(b.month))
    .map((r) => ({
      month: formatMonthLabel(r.month),
      revenue: Number(r.revenue) || 0,
      rating: r.rating_avg !== null ? Number(r.rating_avg) : null,
      plans: r.sessions_completed || 0,
    }));
}

/** Format a YYYY-MM string to a short label like "Jan 26". */
export function formatMonthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  if (Number.isNaN(y) || Number.isNaN(m)) return month;
  const names = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return `${names[m - 1] ?? month} ${String(y).slice(2)}`;
}

interface TrendChartProps {
  title: string;
  data: { month: string; value: number | null }[];
  color: string;
  valueFormatter?: (v: number) => string;
  yLabel?: string;
}

export function TrendChart({
  title,
  data,
  color,
  valueFormatter,
}: TrendChartProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      </CardHeader>
      <CardBody>
        {data.length === 0 ? (
          <p className="text-sm text-gray-500">No data available.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v) => (valueFormatter ? valueFormatter(v) : String(v))}
                />
                <Tooltip
                  formatter={(v) => [
                    valueFormatter ? valueFormatter(Number(v)) : String(v),
                    title,
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

interface PlansBarChartProps {
  data: { month: string; plans: number }[];
}

export function PlansBarChart({ data }: PlansBarChartProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-lg font-semibold text-gray-900">Sessions completed</h3>
      </CardHeader>
      <CardBody>
        {data.length === 0 ? (
          <p className="text-sm text-gray-500">No data available.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => [String(v), "Sessions"]} />
                <Legend />
                <Bar dataKey="plans" name="Sessions" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
