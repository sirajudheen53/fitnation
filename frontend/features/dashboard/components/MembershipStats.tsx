"use client";

import {
  Pie,
  PieChart,
  ResponsiveContainer,
  Cell,
  Tooltip,
  Legend,
} from "recharts";
import { Card, CardHeader, CardBody } from "@/components/ui";
import type { MembershipStatsData } from "@/types/dashboard";

const COLORS = ["#4f46e5", "#f59e0b", "#ef4444"];

interface MembershipStatsProps {
  data: MembershipStatsData;
  loading?: boolean;
}

export function MembershipStats({ data, loading = false }: MembershipStatsProps) {
  if (loading) {
    return (
      <Card>
        <CardBody>
          <div className="h-64 animate-pulse rounded-lg bg-gray-100" />
        </CardBody>
      </Card>
    );
  }

  const breakdown = data?.breakdown ?? { active: 0, expired: 0, cancelled: 0 };
  const pieData = [
    { name: "Active", value: breakdown.active },
    { name: "Expired", value: breakdown.expired },
    { name: "Cancelled", value: breakdown.cancelled },
  ];

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Memberships</h2>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-lg bg-green-50 p-3 text-center">
            <p className="text-2xl font-semibold text-green-700">{breakdown.active}</p>
            <p className="text-xs text-green-600">Active</p>
          </div>
          <div className="rounded-lg bg-amber-50 p-3 text-center">
            <p className="text-2xl font-semibold text-amber-700">{breakdown.expired}</p>
            <p className="text-xs text-amber-600">Expired</p>
          </div>
          <div className="rounded-lg bg-red-50 p-3 text-center">
            <p className="text-2xl font-semibold text-red-700">{breakdown.cancelled}</p>
            <p className="text-xs text-red-600">Cancelled</p>
          </div>
        </div>

        <div className="mt-4">
          {data?.plan_distribution?.length ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.plan_distribution.map((d) => ({
                      name: d.plan,
                      value: d.count,
                    }))}
                    dataKey="value"
                    nameKey="name"
                    outerRadius={80}
                    label
                  >
                    {data.plan_distribution.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No plan distribution data.</p>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
