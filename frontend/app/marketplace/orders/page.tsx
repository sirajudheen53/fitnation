"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Package, ArrowRight } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert, Spinner, Badge } from "@/components/ui";
import { fetchOrders, errorMessage } from "@/lib/api";
import type { Order, OrderStatus } from "@/types/marketplace";

const STATUS_VARIANT: Record<OrderStatus, "default" | "info" | "success" | "warning" | "danger"> = {
  pending: "warning",
  processing: "info",
  shipped: "info",
  delivered: "success",
  cancelled: "danger",
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function OrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/marketplace/orders");
      return;
    }
    fetchOrders(token)
      .then((data) => setOrders(data.results))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <DashboardLayout title="Order History">
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error ? (
        <Alert variant="error">{error}</Alert>
      ) : orders.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-white py-20 text-center shadow-sm">
          <Package className="h-12 w-12 text-gray-300" />
          <p className="mt-4 text-lg font-medium text-gray-900">
            No orders yet
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Your purchases will appear here.
          </p>
          <Link href="/marketplace" className="mt-6">
            <span className="text-sm font-medium text-brand-600 hover:text-brand-700">
              Start shopping
            </span>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <Link key={order.id} href={`/marketplace/orders/${order.id}`}>
              <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-brand-300">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-gray-900">
                      {order.order_number}
                    </p>
                    <p className="text-sm text-gray-500">
                      {formatDate(order.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <Badge variant={STATUS_VARIANT[order.status]}>
                      {order.status}
                    </Badge>
                    <span className="font-semibold text-gray-900">
                      ₹{order.total}
                    </span>
                    <ArrowRight className="h-4 w-4 text-gray-400" />
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}
