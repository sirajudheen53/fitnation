"use client";

import Link from "next/link";
import { Star, TrendingUp, Users } from "lucide-react";
import { Card, CardHeader, CardBody } from "@/components/ui";
import type { TrainerOverviewData } from "@/types/dashboard";

interface TrainerOverviewProps {
  trainers: TrainerOverviewData[];
  loading?: boolean;
}

export function formatTrainerRevenue(value: number | string): string {
  const num = Number(value) || 0;
  return `₹${num.toLocaleString()}`;
}

export function formatTrainerRating(value: number | string): string {
  const r = Number(value);
  if (Number.isNaN(r)) return "—";
  return r.toFixed(1);
}

export function TrainerOverview({ trainers, loading = false }: TrainerOverviewProps) {
  // Defensive: a malformed API payload must never crash the dashboard render.
  const items = Array.isArray(trainers) ? trainers : [];

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
        <h2 className="text-lg font-semibold text-gray-900">Top trainers</h2>
      </CardHeader>
      <CardBody>
        {items.length === 0 ? (
          <p className="text-sm text-gray-500">No trainers to show.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {items.map((trainer) => (
              <li key={trainer.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
                    {trainer.name.charAt(0)}
                  </div>
                  <div>
                    <Link
                      href={`/trainers/${trainer.id}`}
                      className="font-medium text-gray-900 hover:text-brand-600"
                    >
                      {trainer.name}
                    </Link>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <Star className="h-3 w-3 text-amber-500" />
                        {formatTrainerRating(trainer.rating)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" />
                        {trainer.active_clients}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 text-sm font-medium text-green-600">
                  <TrendingUp className="h-3.5 w-3.5" />
                  {formatTrainerRevenue(trainer.revenue)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
