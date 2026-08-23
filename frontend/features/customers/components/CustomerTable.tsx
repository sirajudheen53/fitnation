"use client";

import { useState } from "react";
import Link from "next/link";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, Edit, Eye, MoreHorizontal, Trash2 } from "lucide-react";
import { Button, Badge } from "@/components/ui";
import type { Customer } from "@/types/customer";

const columnHelper = createColumnHelper<Customer>();

export function getCustomerMembershipStatus(customer: Customer): {
  label: string;
  variant: "success" | "warning" | "danger" | "default";
} {
  if (!customer.is_active) {
    return { label: "Inactive", variant: "danger" };
  }
  return { label: "Active", variant: "success" };
}

export function getCustomerDisplayName(customer: Customer): string {
  const name = `${customer.first_name || ""} ${customer.last_name || ""}`.trim();
  return name || customer.email;
}

interface CustomerTableProps {
  customers: Customer[];
  onDelete?: (customer: Customer) => void;
  loading?: boolean;
}

export function CustomerTable({ customers, onDelete, loading }: CustomerTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = [
    columnHelper.accessor((row) => getCustomerDisplayName(row), {
      id: "name",
      header: "Name",
      cell: ({ row }) => (
        <div>
          <div className="font-medium text-gray-900">{getCustomerDisplayName(row.original)}</div>
          <div className="text-sm text-gray-500">{row.original.email}</div>
        </div>
      ),
    }),
    columnHelper.accessor("phone", {
      header: "Phone",
      cell: ({ getValue }) => <span className="text-sm text-gray-700">{getValue() || "—"}</span>,
    }),
    columnHelper.accessor("gender", {
      header: "Gender",
      cell: ({ getValue }) => {
        const value = getValue();
        if (!value) return <span className="text-sm text-gray-500">—</span>;
        const labels: Record<string, string> = {
          male: "Male",
          female: "Female",
          other: "Other",
          prefer_not_to_say: "Prefer not to say",
        };
        return <span className="text-sm text-gray-700">{labels[value] || value}</span>;
      },
    }),
    columnHelper.display({
      id: "membership_status",
      header: "Membership status",
      cell: ({ row }) => {
        const { label, variant } = getCustomerMembershipStatus(row.original);
        return <Badge variant={variant}>{label}</Badge>;
      },
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex items-center justify-end gap-2">
          <Link href={`/customers/${row.original.id}`}>
            <Button variant="ghost" size="sm" aria-label="View customer">
              <Eye className="h-4 w-4" />
            </Button>
          </Link>
          <Link href={`/customers/${row.original.id}/edit`}>
            <Button variant="ghost" size="sm" aria-label="Edit customer">
              <Edit className="h-4 w-4" />
            </Button>
          </Link>
          {onDelete && (
            <Button
              variant="ghost"
              size="sm"
              aria-label="Delete customer"
              onClick={() => onDelete(row.original)}
            >
              <Trash2 className="h-4 w-4 text-red-500" />
            </Button>
          )}
        </div>
      ),
    }),
  ];

  const table = useReactTable({
    data: customers,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <MoreHorizontal className="h-8 w-8 animate-pulse text-gray-400" />
      </div>
    );
  }

  if (customers.length === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center rounded-xl border border-gray-200 bg-white">
        <p className="text-sm text-gray-500">No customers found.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id} className="px-4 py-3 font-medium text-gray-700">
                  {header.isPlaceholder ? null : (
                    <button
                      className={`flex items-center gap-1 ${header.column.getCanSort() ? "cursor-pointer" : ""}`}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getCanSort() && (
                        <ArrowUpDown className="h-3.5 w-3.5 text-gray-400" />
                      )}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-gray-100">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-3">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
        <div className="text-sm text-gray-500">
          Page {table.getState().pagination.pageIndex + 1} of{" "}
          {table.getPageCount() || 1}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
