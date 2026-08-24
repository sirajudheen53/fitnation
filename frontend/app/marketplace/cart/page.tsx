"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShoppingCart, Trash2, Package, ArrowRight } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchCart, errorMessage } from "@/lib/api";
import type { Cart } from "@/types/marketplace";

export default function CartPage() {
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCart = () => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/marketplace/cart");
      return;
    }
    setLoading(true);
    setError(null);
    fetchCart(token)
      .then(setCart)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCheckout = () => {
    router.push("/marketplace/orders");
  };

  return (
    <DashboardLayout
      title="Shopping Cart"
      actions={
        <Link
          href="/marketplace"
          className="text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          Continue shopping
        </Link>
      }
    >
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error ? (
        <Alert variant="error">{error}</Alert>
      ) : !cart || cart.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-white py-20 text-center shadow-sm">
          <ShoppingCart className="h-12 w-12 text-gray-300" />
          <p className="mt-4 text-lg font-medium text-gray-900">
            Your cart is empty
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Browse the marketplace to add products.
          </p>
          <Link href="/marketplace" className="mt-6">
            <Button variant="primary">Browse products</Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {cart.items.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
              >
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100">
                  {item.product_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.product_image_url}
                      alt={item.product_name}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <Package className="h-6 w-6 text-gray-300" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-gray-900">
                    {item.product_name}
                  </p>
                  <p className="text-sm text-gray-500">
                    ₹{item.product_price} × {item.quantity}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-gray-900">₹{item.subtotal}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="h-fit rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900">Order summary</h3>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between text-gray-600">
                <span>Items ({cart.item_count})</span>
                <span>₹{cart.total}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Shipping</span>
                <span>Calculated at checkout</span>
              </div>
              <div className="flex justify-between border-t border-gray-100 pt-3 text-base font-semibold text-gray-900">
                <span>Total</span>
                <span>₹{cart.total}</span>
              </div>
            </div>
            <Button className="mt-6 w-full" onClick={handleCheckout}>
              Checkout <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
