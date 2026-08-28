"use client";

import { Card, CardHeader, CardBody } from "@/components/ui";
import type { TopCustomer } from "@/types/analytics";

interface TopCustomersTableProps {
  data: TopCustomer[];
  loading?: boolean;
}

/** Format a paise amount as an INR rupee string. */
export function formatSpend(amount: number): string {
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

/** Render the top customers table (FBOS-030). */
export function TopCustomersTable({ data, loading = false }: TopCustomersTableProps) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Top Customers</h2>
      </CardHeader>
      <CardBody>
        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-gray-500">No customer data available.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                  <th className="py-2 pr-4 font-medium">Rank</th>
                  <th className="py-2 pr-4 font-medium">Customer</th>
                  <th className="py-2 font-medium text-right">Total spent</th>
                </tr>
              </thead>
              <tbody>
                {data.map((customer, index) => (
                  <tr key={customer.customer_id} className="border-b border-gray-100 last:border-0">
                    <td className="py-2.5 pr-4 text-gray-500">{index + 1}</td>
                    <td className="py-2.5 pr-4 font-medium text-gray-900">
                      {customer.customer_name ?? `Customer #${customer.customer_id}`}
                    </td>
                    <td className="py-2.5 text-right text-gray-900">
                      {formatSpend(customer.total_spent)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
