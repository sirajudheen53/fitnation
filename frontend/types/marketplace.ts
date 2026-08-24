/**
 * Marketplace type definitions — FBOS-016.
 */

export interface MarketplaceProduct {
  id: number;
  name: string;
  description: string;
  category: string;
  price: string;
  compare_at_price: string | null;
  image_url: string | null;
  stock: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MarketplaceProductListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: MarketplaceProduct[];
}

export interface CartItem {
  id: number;
  product: number;
  product_name: string;
  product_price: string;
  product_image_url: string | null;
  quantity: number;
  subtotal: string;
}

export interface Cart {
  id: number;
  items: CartItem[];
  total: string;
  item_count: number;
}

export interface OrderItem {
  id: number;
  product: number;
  product_name: string;
  product_price: string;
  quantity: number;
  line_total: string;
}

export type OrderStatus =
  | "pending"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled";

export interface Order {
  id: number;
  order_number: string;
  status: OrderStatus;
  items: OrderItem[];
  subtotal: string;
  shipping_cost: string;
  total: string;
  shipping_address: string | null;
  tracking_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Order[];
}
