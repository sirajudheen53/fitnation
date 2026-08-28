"use client";

import { Card, CardHeader, CardBody } from "@/components/ui";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { RevenueReport } from "@/types/analytics";

interface RevenueChartProps {
  data: RevenueReport[];
  periodLabel?: string; // e.g., "Daily", "Weekly", "Monthly"
}

export function RevenueChart({ data, periodLabel = "Revenue" }: RevenueChartProps) {
  // Transform data for recharts – ensure sorted by period
  const sorted = [...data].sort((a, b) => new Date(a.period).getTime() - new Date(b.period).getTime());

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">{periodLabel}</h2>
      </CardHeader>
      <CardBody>
        <div className="h-64 w-full">
          <ResponsiveContainer>
            <LineChart data={sorted} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" tickFormatter={val => new Date(val).toLocaleDateString()} />
              <YAxis tickFormatter={val => `${val}`} />
              <Tooltip labelFormatter={val => new Date(val as string).toLocaleDateString()} />
              <Line type="monotone" dataKey="amount" stroke="#4f46e5" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardBody>
    </Card>
  );
}
