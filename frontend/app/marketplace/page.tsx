"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, ShoppingBag, ShoppingCart, Package } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert, Spinner, Badge } from "@/components/ui";
import { fetchProducts, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { MarketplaceProduct } from "@/types/marketplace";

const CATEGORIES = [
  "Supplements",
  "Apparel",
  "Equipment",
  "Recovery",
  "Nutrition",
  "Accessories",
];

export default function MarketplacePage() {
  const router = useRouter();
  const [products, setProducts] = useState<MarketplaceProduct[]>([]);
  const [category, setCategory] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/marketplace");
      return;
    }
  }, [router]);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(handler);
  }, [search]);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;

    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params: { category?: string; search?: string } = {};
        if (category && category !== "All") params.category = category;
        if (debouncedSearch) params.search = debouncedSearch;
        const res = await fetchProducts(authToken, params);
        if (active) setProducts(res.results);
      } catch (err) {
        if (active) setError(errorMessage(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [category, debouncedSearch]);

  const formatPriceInner = formatPrice;

  return (
    <DashboardLayout
      title="Marketplace"
      actions={
        <>
          <Link href="/marketplace/cart">
            <Button variant="outline" size="sm">
              <ShoppingCart className="h-4 w-4" /> Cart
            </Button>
          </Link>
          <Link href="/marketplace/orders">
            <Button variant="outline" size="sm">
              <Package className="h-4 w-4" /> Orders
            </Button>
          </Link>
        </>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}

      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full md:max-w-xs">
          <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
            <Search className="h-4 w-4" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products..."
            aria-label="Search products"
            className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setCategory(cat === "All" ? "" : cat)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                (category === cat) || (cat === "All" && category === "")
                  ? "bg-brand-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-200"
              }`}
              aria-pressed={(category === cat) || (cat === "All" && category === "")}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}

      {!loading && products.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <ShoppingBag className="mx-auto mb-3 h-10 w-10 text-gray-300" />
          <p className="text-sm text-gray-500">No products found.</p>
        </div>
      )}

      {!loading && products.length > 0 && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {products.map((product) => (
            <Link
              key={product.id}
              href={`/marketplace/${product.id}`}
              className="group overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="aspect-square w-full overflow-hidden bg-gray-100">
                {product.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-brand-50">
                    <ShoppingBag className="h-12 w-12 text-brand-300" />
                  </div>
                )}
              </div>
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-medium text-gray-900">{product.name}</h3>
                    <Badge className="mt-1">{product.category}</Badge>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-brand-700">
                      {formatPrice(product.price)}
                    </div>
                    {product.compare_at_price && (
                      <div className="text-xs text-gray-400 line-through">
                        {formatPrice(product.compare_at_price)}
                      </div>
                    )}
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

function formatPrice(price: string | number): string {
  const value = typeof price === "string" ? price : String(price);
  return `$${Number(value).toFixed(2)}`;
}
