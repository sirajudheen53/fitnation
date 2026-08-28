"use client";

import { Card, CardHeader, CardBody } from "@/components/ui";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { MembershipFunnel } from "@/types/analytics";

interface MembershipFunnelChartProps {
  data: MembershipFunnel[];
}

export function MembershipFunnelChart({ data }: MembershipFunnelChartProps) {
  // Ensure order: prospect, trial, active, cancelled (as defined in backend)
  const order = ["prospect", "trial", "active", "cancelled"];
  const sorted = order
    .map(stage => data.find(d => d.stage === stage) || { stage, count: 0 })
    .filter(Boolean);

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Membership Funnel</h2>
      </CardHeader>
      <CardBody>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={sorted} layout="vertical" margin={{ top: 20, right: 30, left: 80, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <YAxis dataKey="stage" type="category" />
            <XAxis type="number" />
            <Tooltip />
            <Bar dataKey="count" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  );
}
