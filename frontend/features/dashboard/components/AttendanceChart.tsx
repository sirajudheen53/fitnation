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
import type { AttendanceDashboardData } from "@/types/dashboard";

interface AttendanceChartProps {
  data: AttendanceDashboardData;
  loading?: boolean;
}

export function AttendanceChart({ data, loading = false }: AttendanceChartProps) {
  if (loading) {
    return (
      <Card>
        <CardBody>
          <div className="h-64 animate-pulse rounded-lg bg-gray-100" />
        </CardBody>
      </Card>
    );
  }

  const peakData = (data?.peak_hours ?? []).map((p) => ({
    label: p.hour,
    checkIns: p.check_ins,
  }));

  const trendData = (data?.weekly_trend ?? []).map((p) => ({
    label: p.hour,
    checkIns: p.check_ins,
  }));

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Peak hours</h2>
      </CardHeader>
      <CardBody>
        {peakData.length === 0 ? (
          <p className="text-sm text-gray-500">No attendance data available.</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={peakData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="checkIns" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
