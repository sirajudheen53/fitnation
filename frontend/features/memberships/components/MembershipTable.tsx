"use client";

import Link from "next/link";
import { Eye, Ban } from "lucide-react";
import { Badge } from "@/components/ui";
import type { Membership, MembershipStatus } from "@/types/membership";

const STATUS_VARIANTS: Record<MembershipStatus, "success" | "warning" | "danger" | "info"> = {
  active: "success",
  pending: "warning",
  expired: "danger",
  cancelled: "info",
};

export function getMembershipStatusLabel(status: MembershipStatus): string {
  const labels: Record<MembershipStatus, string> = {
    active: "Active",
    pending: "Pending",
    expired: "Expired",
    cancelled: "Cancelled",
  };
  return labels[status];
}

export function formatMembershipDate(date: string | null): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString();
}

interface MembershipTableProps {
  memberships: Membership[];
  onCancel?: (membership: Membership) => void;
  loading?: boolean;
}

export function MembershipTable({
  memberships,
  onCancel,
  loading = false,
}: MembershipTableProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-sm text-gray-500">
        Loading memberships…
      </div>
    );
  }

  if (memberships.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
        <p className="text-sm text-gray-500">No memberships yet.</p>
        <p className="mt-1 text-sm text-gray-400">Assign a membership to a customer to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-6 py-3 font-medium">Customer</th>
            <th className="px-6 py-3 font-medium">Plan</th>
            <th className="px-6 py-3 font-medium">Start</th>
            <th className="px-6 py-3 font-medium">End</th>
            <th className="px-6 py-3 font-medium">Price</th>
            <th className="px-6 py-3 font-medium">Status</th>
            <th className="px-6 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {memberships.map((membership) => (
            <tr key={membership.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 font-medium text-gray-900">
                {membership.customer_name}
              </td>
              <td className="px-6 py-4 text-gray-700">{membership.plan_name}</td>
              <td className="px-6 py-4 text-gray-600">
                {formatMembershipDate(membership.start_date)}
              </td>
              <td className="px-6 py-4 text-gray-600">
                {formatMembershipDate(membership.end_date)}
              </td>
              <td className="px-6 py-4 text-gray-700">
                ₹{membership.price.toLocaleString()}
              </td>
              <td className="px-6 py-4">
                <Badge variant={STATUS_VARIANTS[membership.status]}>
                  {getMembershipStatusLabel(membership.status)}
                </Badge>
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                  <Link
                    href={`/customers/${membership.customer_id}`}
                    className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                    aria-label="View customer"
                  >
                    <Eye className="h-4 w-4" />
                  </Link>
                  {membership.status === "active" && onCancel && (
                    <button
                      onClick={() => onCancel(membership)}
                      className="rounded-lg p-2 text-red-500 hover:bg-red-50 hover:text-red-700"
                      aria-label="Cancel membership"
                    >
                      <Ban className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
