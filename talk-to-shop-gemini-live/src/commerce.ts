/**
 * Authoritative Commerce Service & Data Layer
 *
 * Core Architectural Principle:
 * The model NEVER directly accesses databases or decides prices, inventory, or order status.
 * All operations execute through these validated, server-side functions.
 */

import { CATALOGUE } from './catalogue.js';

export interface Product {
  id: string;
  name: string;
  category: string;
  priceInr: number;
  /** Omitted for products without a battery (e.g. security cameras). */
  batteryHours?: number;
  /** Audio products only. */
  ancType?: string;
  weightGrams: number;
  /** Short, category-specific spec lines shown as pills (e.g. screen, storage, camera). */
  highlights?: string[];
  rating: number;
  reviewsCount: number;
  stock: number;
  imageUrl: string;
  description: string;
  tags: string[];
}

export interface CartItem {
  product: Product;
  quantity: number;
  itemSubtotalInr: number;
}

export interface Cart {
  items: CartItem[];
  itemCount: number;
  subtotalInr: number;
  gstInr: number;
  shippingInr: number;
  totalInr: number;
}

export interface Address {
  id: string;
  label: string;
  recipient: string;
  street: string;
  city: string;
  state: string;
  pincode: string;
  isDefault: boolean;
}

export interface Order {
  orderId: string;
  items: CartItem[];
  totalInr: number;
  shippingAddress: Address;
  paymentMethod: string;
  status: 'confirmed' | 'processing' | 'shipped';
  estimatedDeliveryDate: string;
  createdAt: string;
}

// ----------------------------------------------------------------------------
// Search helpers
// ----------------------------------------------------------------------------
const STOPWORDS = new Set(['for', 'the', 'and', 'with', 'under', 'best', 'some', 'any']);

/** Lowercase keywords with trailing plural 's' dropped, so "smartwatches" matches "smartwatch". */
function tokenize(query?: string): string[] {
  return (query || '')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 2 && !STOPWORDS.has(t))
    .map((t) => t.replace(/s$/, ''));
}

/** Everything a keyword can match against, built once per product. */
const haystackCache = new Map<string, string>();
function haystack(p: Product): string {
  let h = haystackCache.get(p.id);
  if (!h) {
    h = [p.name, p.category.replace(/_/g, ' '), p.description, ...p.tags, ...(p.highlights ?? [])].join(' ').toLowerCase();
    haystackCache.set(p.id, h);
  }
  return h;
}

// ----------------------------------------------------------------------------
// Authoritative Customer Saved Addresses
// ----------------------------------------------------------------------------
export const SAVED_ADDRESSES: Address[] = [
  {
    id: 'addr_blr_home',
    label: 'Home',
    recipient: 'Aditya Joshi',
    street: 'Flat 402, Green Glen Heights, Bellandur',
    city: 'Bengaluru',
    state: 'Karnataka',
    pincode: '560103',
    isDefault: true,
  },
  {
    id: 'addr_mum_studio',
    label: 'Orbit Studio',
    recipient: 'Aditya Joshi',
    street: 'Unit 12, Andheri Kurla Road, Marol',
    city: 'Mumbai',
    state: 'Maharashtra',
    pincode: '400059',
    isDefault: false,
  },
];

// ----------------------------------------------------------------------------
// Session Cart State Manager
// ----------------------------------------------------------------------------
class CommerceStore {
  private cartItems: Map<string, number> = new Map();
  private orders: Order[] = [];

  // Reset store for fresh demo runs
  public reset(): void {
    this.cartItems.clear();
    this.orders = [];
  }

  // 1. Search Products
  public searchProducts(params: {
    query?: string;
    category?: string;
    maxPriceInr?: number;
    minBatteryHours?: number;
    ancRequired?: boolean;
  }): { count: number; products: Product[] } {
    const tokens = tokenize(params.query);
    const results = Object.values(CATALOGUE).filter((p) => {
      if (params.category && p.category !== params.category) return false;
      if (params.maxPriceInr && p.priceInr > params.maxPriceInr) return false;
      if (params.minBatteryHours && (p.batteryHours ?? 0) < params.minBatteryHours) return false;
      if (params.ancRequired && !(p.ancType ?? '').toLowerCase().includes('anc')) return false;

      return tokens.every((t) => haystack(p).includes(t));
    });

    return {
      count: results.length,
      products: results,
    };
  }

  // 2. Get Product Details
  public getProductDetails(productId: string): Product | null {
    return CATALOGUE[productId] || null;
  }

  // 3. Compare Products
  public compareProducts(productIds: string[]): { compared: Product[]; diff: Record<string, unknown> } {
    const products = productIds.map((id) => CATALOGUE[id]).filter(Boolean) as Product[];
    return {
      compared: products,
      diff: {
        priceSpreadInr: products.map((p) => ({ name: p.name, price: p.priceInr })),
        batteryComparisonHours: products.map((p) => ({ name: p.name, batteryHours: p.batteryHours })),
        noiseCancellation: products.map((p) => ({ name: p.name, anc: p.ancType })),
        keySpecs: products.map((p) => ({ name: p.name, highlights: p.highlights })),
        recommendation: products.length > 0 ? products[0].name : 'None',
      },
    };
  }

  // 4. Check Inventory
  public checkInventory(productId: string, pincode?: string): { inStock: boolean; availableQty: number; warehouseCity: string; estimatedDays: number } {
    const p = CATALOGUE[productId];
    if (!p) {
      return { inStock: false, availableQty: 0, warehouseCity: 'Unknown', estimatedDays: 0 };
    }
    const isLocal = pincode?.startsWith('560') || pincode?.startsWith('400');
    return {
      inStock: p.stock > 0,
      availableQty: p.stock,
      warehouseCity: 'Bengaluru Hub #4',
      estimatedDays: isLocal ? 1 : 2,
    };
  }

  // 5. Add to Cart (Authoritative server validation)
  public addToCart(productId: string, quantity: number = 1): { success: boolean; cart: Cart; message: string } {
    const product = CATALOGUE[productId];
    if (!product) {
      return { success: false, cart: this.getCart(), message: `Invalid product ID: ${productId}` };
    }
    const cur = this.cartItems.get(productId) || 0;
    const requested = cur + Math.max(1, quantity);

    if (requested > product.stock) {
      return {
        success: false,
        cart: this.getCart(),
        message: `Only ${product.stock} units of ${product.name} are available in stock.`,
      };
    }

    this.cartItems.set(productId, requested);
    return {
      success: true,
      cart: this.getCart(),
      message: `Added ${quantity}x ${product.name} to cart at ₹${product.priceInr.toLocaleString('en-IN')}.`,
    };
  }

  // 6. Get Cart
  public getCart(): Cart {
    const items: CartItem[] = [];
    let subtotal = 0;

    for (const [id, qty] of this.cartItems.entries()) {
      const p = CATALOGUE[id];
      if (p) {
        const itemSub = p.priceInr * qty;
        subtotal += itemSub;
        items.push({
          product: p,
          quantity: qty,
          itemSubtotalInr: itemSub,
        });
      }
    }

    const gst = Math.round(subtotal * 0.18);
    const shipping = subtotal > 1500 || subtotal === 0 ? 0 : 99;
    const total = subtotal + gst + shipping;

    return {
      items,
      itemCount: items.reduce((acc, i) => acc + i.quantity, 0),
      subtotalInr: subtotal,
      gstInr: gst,
      shippingInr: shipping,
      totalInr: total,
    };
  }

  // 7. Check Delivery
  public checkDelivery(pincode: string): { pincode: string; isServiceable: boolean; shippingCostInr: number; estimatedDeliveryText: string } {
    const cleanPin = (pincode || '560103').replace(/\D/g, '');
    const isServiceable = cleanPin.length === 6;
    return {
      pincode: cleanPin,
      isServiceable,
      shippingCostInr: 0, // Free delivery for demo items
      estimatedDeliveryText: cleanPin.startsWith('560') ? 'Tomorrow by 2:00 PM (Express Hub)' : 'Within 2 business days',
    };
  }

  // 8. Get Saved Addresses
  public getSavedAddresses(): Address[] {
    return SAVED_ADDRESSES;
  }

  // 9. Place Order (Transaction Safety & Explicit Confirmation)
  public placeOrder(params: {
    addressId?: string;
    paymentMethod?: string;
    userConfirmed: boolean;
  }): { success: boolean; order?: Order; message: string } {
    if (!params.userConfirmed) {
      return {
        success: false,
        message: 'Order was not placed: User explicit confirmation is strictly required prior to transaction execution.',
      };
    }

    const cart = this.getCart();
    if (cart.items.length === 0) {
      return {
        success: false,
        message: 'Cannot place order: Shopping cart is currently empty.',
      };
    }

    const addr = SAVED_ADDRESSES.find((a) => a.id === params.addressId) || SAVED_ADDRESSES[0];
    const orderId = `ORD-2026-${Math.floor(100000 + Math.random() * 900000)}`;

    // Deduct inventory
    for (const item of cart.items) {
      const p = CATALOGUE[item.product.id];
      if (p) p.stock -= item.quantity;
    }

    const newOrder: Order = {
      orderId,
      items: [...cart.items],
      totalInr: cart.totalInr,
      shippingAddress: addr,
      paymentMethod: params.paymentMethod || 'Google Pay (UPI Verified)',
      status: 'confirmed',
      estimatedDeliveryDate: 'Tomorrow, by 2:00 PM',
      createdAt: new Date().toISOString(),
    };

    this.orders.push(newOrder);
    this.cartItems.clear(); // Clear cart after successful transaction

    return {
      success: true,
      order: newOrder,
      message: `Order #${orderId} confirmed! Total ₹${newOrder.totalInr.toLocaleString('en-IN')} paid via ${newOrder.paymentMethod}. Arriving ${newOrder.estimatedDeliveryDate} at ${addr.street}, ${addr.city}.`,
    };
  }
}

export const commerce = new CommerceStore();
