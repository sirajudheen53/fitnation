"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { ShoppingCart, Package, ArrowLeft, Minus, Plus } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert, Spinner, Badge } from "@/components/ui";
import { fetchProduct, addToCart, errorMessage } from "@/lib/api";
import type { MarketplaceProduct } from "@/types/marketplace";

export default function ProductDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const productId = params?.id;

  const [product, setProduct] = useState<MarketplaceProduct | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace(`/login?next=/marketplace/${productId}`);
      return;
    }
    if (!productId) return;

    fetchProduct(productId, token)
      .then((data) => setProduct(data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [productId, router]);

  const handleAddToCart = async () => {
    const token = getToken();
    if (!token || !product) return;
    setAdding(true);
    setError(null);
    try {
      await addToCart(token, product.id, quantity);
      setAdded(true);
      setTimeout(() => setAdded(false), 2000);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAdding(false);
    }
  };

  return (
    <DashboardLayout title={product?.name ?? "Product"}>
      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error && !product ? (
        <Alert variant="error">{error}</Alert>
      ) : !product ? (
        <Alert variant="warning">Product not found.</Alert>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            {product.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={product.image_url}
                alt={product.name}
                className="h-80 w-full object-cover"
              />
            ) : (
              <div className="flex h-80 w-full items-center justify-center bg-gray-100">
                <Package className="h-16 w-16 text-gray-300" />
              </div>
            )}
          </div>

          <div>
            <Link
              href="/marketplace"
              className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800"
            >
              <ArrowLeft className="h-4 w-4" /> Back to marketplace
            </Link>

            <div className="mt-4">
              <Badge variant="info">{product.category}</Badge>
              <h1 className="mt-3 text-2xl font-bold text-gray-900">
                {product.name}
              </h1>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-brand-600">
                  ₹{product.price}
                </span>
                {product.compare_at_price && (
                  <span className="text-sm text-gray-400 line-through">
                    ₹{product.compare_at_price}
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm text-gray-500">
                {product.stock > 0
                  ? `${product.stock} in stock`
                  : "Out of stock"}
              </p>
            </div>

            <p className="mt-6 text-gray-700">{product.description}</p>

            <div className="mt-8 flex items-center gap-4">
              <div className="flex items-center rounded-lg border border-gray-300">
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  className="p-2 text-gray-500 hover:text-gray-800"
                  aria-label="Decrease quantity"
                >
                  <Minus className="h-4 w-4" />
                </button>
                <span className="w-10 text-center text-sm font-medium">
                  {quantity}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setQuantity((q) =>
                      product.stock > 0 ? Math.min(product.stock, q + 1) : q,
                    )
                  }
                  className="p-2 text-gray-500 hover:text-gray-800"
                  aria-label="Increase quantity"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>

              <Button
                onClick={handleAddToCart}
                disabled={adding || product.stock === 0}
              >
                <ShoppingCart className="mr-2 h-4 w-4" />
                {adding
                  ? "Adding..."
                  : added
                    ? "Added to cart!"
                    : "Add to cart"}
              </Button>
            </div>

            {error && <Alert variant="error" className="mt-4">{error}</Alert>}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
