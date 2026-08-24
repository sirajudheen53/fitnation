"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { Package, ArrowLeft, MapPin, Truck } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Alert, Spinner, Badge } from "@/components/ui";
import { fetchOrder, errorMessage } from "@/lib/api";
import type { Order, OrderStatus } from "@/types/marketplace";

const STATUS_VARIANT: Record<OrderStatus, "default" | "info" | "success" | "warning" | "danger"> = {
  pending: "warning",
  processing: "info",
  shipped: "info",
  delivered: "success",
  cancelled: "danger",
};

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const orderId = params?.id;

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace(`/login?next=/marketplace/orders/${orderId}`);
      return;
    }
    if (!orderId) return;

    fetchOrder(orderId, token)
      .then(setOrder)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [orderId, router]);

  return (
    <DashboardLayout title="Order Detail">
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error && !order ? (
        <Alert variant="error">{error}</Alert>
      ) : !order ? (
        <Alert variant="warning">Order not found.</Alert>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Link
              href="/marketplace/orders"
              className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800"
            >
              <ArrowLeft className="h-4 w-4" /> Back to orders
            </Link>
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold text-gray-900">
                {order.order_number}
              </span>
              <Badge variant={STATUS_VARIANT[order.status]}>
                {order.status}
              </Badge>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-100 px-6 py-4">
                <h3 className="font-semibold text-gray-900">Items</h3>
              </div>
              <div className="divide-y divide-gray-100">
                {order.items.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-3">
                      <Package className="h-5 w-5 text-gray-300" />
                      <div>
                        <p className="font-medium text-gray-900">
                          {item.product_name}
                        </p>
                        <p className="text-sm text-gray-500">
                          ₹{item.product_price} × {item.quantity}
                        </p>
                      </div>
                    </div>
                    <span className="font-semibold text-gray-900">
                      ₹{item.line_total}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900">Summary</h3>
                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between text-gray-600">
                    <span>Subtotal</span>
                    <span>₹{order.subtotal}</span>
                  </div>
                  <div className="flex justify-between text-gray-600">
                    <span>Shipping</span>
                    <span>₹{order.shipping_cost}</span>
                  </div>
                  <div className="flex justify-between border-t border-gray-100 pt-3 text-base font-semibold text-gray-900">
                    <span>Total</span>
                    <span>₹{order.total}</span>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                <h3 className="flex items-center gap-2 font-semibold text-gray-900">
                  <MapPin className="h-4 w-4 text-gray-400" /> Shipping address
                </h3>
                <p className="mt-3 text-sm text-gray-700">
                  {order.shipping_address ?? "Not provided"}
                </p>
                {order.tracking_number && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-gray-600">
                    <Truck className="h-4 w-4 text-gray-400" />
                    Tracking: {order.tracking_number}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
