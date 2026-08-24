"use client";

import Link from "next/link";
import { Pencil, Trash2, MapPin } from "lucide-react";
import { Badge, Button } from "@/components/ui";
import type { Branch } from "@/types/branch";

/** Format a full address from a branch. */
export function formatBranchAddress(branch: Pick<Branch, "city" | "state" | "postal_code">): string {
  return [branch.city, branch.state, branch.postal_code].filter(Boolean).join(", ") || "—";
}

/** Format a time string (e.g. "05:00:00" or "05:00") to 12-hour label. */
export function formatBranchTime(time: string | null | undefined): string {
  if (!time) return "—";
  const [h, m] = time.split(":").map(Number);
  if (Number.isNaN(h)) return time;
  const period = h >= 12 ? "PM" : "AM";
  const hour = h % 12 === 0 ? 12 : h % 12;
  const minutes = m !== undefined && !Number.isNaN(m) ? `:${String(m).padStart(2, "0")}` : "";
  return `${hour}${minutes} ${period}`;
}

/** Return a badge variant for a branch's active state. */
export function getBranchStatus(branch: Pick<Branch, "is_active">): {
  label: string;
  variant: "success" | "danger";
} {
  return branch.is_active
    ? { label: "Active", variant: "success" }
    : { label: "Inactive", variant: "danger" };
}

interface BranchTableProps {
  branches: Branch[];
  onDelete?: (branch: Branch) => void;
}

export function BranchTable({ branches, onDelete }: BranchTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Branch</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Address</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Phone</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Hours</th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
            <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {branches.map((branch) => {
            const status = getBranchStatus(branch);
            return (
              <tr key={branch.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link
                    href={`/branches/${branch.id}`}
                    className="font-medium text-gray-900 hover:text-brand-700"
                  >
                    {branch.name}
                  </Link>
                  {branch.is_headquarters && (
                    <Badge variant="info" className="ml-2">
                      HQ
                    </Badge>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  <span className="inline-flex items-start gap-1">
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
                    {formatBranchAddress(branch)}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600">{branch.phone || "—"}</td>
                <td className="px-4 py-3 text-gray-600">
                  {formatBranchTime(branch.opening_time)} – {formatBranchTime(branch.closing_time)}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={status.variant}>{status.label}</Badge>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <Link href={`/branches/${branch.id}/edit`} aria-label={`Edit ${branch.name}`}>
                      <Button size="sm" variant="ghost">
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </Link>
                    {onDelete && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onDelete(branch)}
                        aria-label={`Delete ${branch.name}`}
                        className="text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
