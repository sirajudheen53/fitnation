"use client";

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
import type { AttendanceSummary } from "@/types/attendance";

interface PeakHoursChartProps {
  summary: AttendanceSummary;
}

export function PeakHoursChart({ summary }: PeakHoursChartProps) {
  const data = summary.labels.map((label, i) => ({
    hour: label,
    checkIns: summary.check_ins[i] ?? 0,
  }));

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Weekly check-ins</h2>
      </CardHeader>
      <CardBody>
        {data.length === 0 ? (
          <p className="text-sm text-gray-500">No data available yet.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="hour" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="checkIns" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
