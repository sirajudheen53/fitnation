"use client";

import Link from "next/link";
import { Star, Users, TrendingUp, Pencil } from "lucide-react";
import { Card, CardBody, Badge } from "@/components/ui";
import type { Trainer } from "@/types/trainer";

interface TrainerCardProps {
  trainer: Trainer;
}

export function formatRating(rating: number | string): string {
  const r = Number(rating);
  if (Number.isNaN(r)) return "—";
  return r.toFixed(1);
}

export function formatRevenue(revenue: number | string): string {
  const num = Number(revenue) || 0;
  return `₹${num.toLocaleString()}`;
}

export function TrainerCard({ trainer }: TrainerCardProps) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-lg font-semibold text-brand-700">
              {trainer.first_name.charAt(0)}
              {trainer.last_name.charAt(0)}
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">
                {trainer.first_name} {trainer.last_name}
              </h3>
              {trainer.specialization && (
                <p className="text-sm text-gray-500">{trainer.specialization}</p>
              )}
            </div>
          </div>
          {trainer.is_active ? (
            <Badge variant="success">Active</Badge>
          ) : (
            <Badge variant="danger">Inactive</Badge>
          )}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-4 border-t border-gray-100 pt-4">
          <div className="flex flex-col items-center">
            <div className="flex items-center gap-1 text-amber-500">
              <Star className="h-4 w-4" />
              <span className="font-semibold text-gray-900">
                {formatRating(trainer.rating)}
              </span>
            </div>
            <span className="mt-1 text-xs text-gray-500">Rating</span>
          </div>
          <div className="flex flex-col items-center">
            <div className="flex items-center gap-1 text-green-600">
              <TrendingUp className="h-4 w-4" />
              <span className="font-semibold text-gray-900">
                {formatRevenue(trainer.revenue)}
              </span>
            </div>
            <span className="mt-1 text-xs text-gray-500">Revenue</span>
          </div>
          <div className="flex flex-col items-center">
            <div className="flex items-center gap-1 text-brand-600">
              <Users className="h-4 w-4" />
              <span className="font-semibold text-gray-900">{trainer.active_clients}</span>
            </div>
            <span className="mt-1 text-xs text-gray-500">Clients</span>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2 border-t border-gray-100 pt-3">
          <Link
            href={`/trainers/${trainer.id}`}
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            View profile
          </Link>
          <Link
            href={`/trainers/${trainer.id}/edit`}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Edit trainer"
          >
            <Pencil className="h-4 w-4" />
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}
