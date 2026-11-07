/**
 * Authoritative Commerce Service & Data Layer
 *
 * Core Architectural Principle:
 * The model NEVER directly accesses databases or decides prices, inventory, or order status.
 * All operations execute through these validated, server-side functions.
 */

export interface Product {
  id: string;
  name: string;
  category: string;
  priceInr: number;
  batteryHours: number;
  ancType: string;
  weightGrams: number;
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
// Seeded Authoritative Product Catalogue
// ----------------------------------------------------------------------------
export const CATALOGUE: Record<string, Product> = {
  prod_tb_x: {
    id: 'prod_tb_x',
    name: 'TravelBeats X',
    category: 'wireless_headphones',
    priceInr: 2799,
    batteryHours: 50,
    ancType: 'Hybrid ANC',
    weightGrams: 255,
    rating: 4.8,
    reviewsCount: 1420,
    stock: 8,
    imageUrl: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80',
    description: 'Foldable over-ear headphones engineered for frequent travellers with 50-hour playback and deep active noise cancellation.',
    tags: ['travel', 'wireless', 'headphones', 'long-battery', 'anc', 'budget', 'airplane'],
  },
  prod_sw_pro: {
    id: 'prod_sw_pro',
    name: 'SoundWave Pro',
    category: 'wireless_headphones',
    priceInr: 2499,
    batteryHours: 40,
    ancType: 'Adaptive ANC',
    weightGrams: 240,
    rating: 4.6,
    reviewsCount: 980,
    stock: 14,
    imageUrl: 'https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&q=80',
    description: 'Lightweight ergonomic travel headphones featuring adaptive noise cancellation and Bluetooth 5.3 multipoint pairing.',
    tags: ['travel', 'wireless', 'headphones', 'multipoint', 'anc', 'budget'],
  },
  prod_af_lite: {
    id: 'prod_af_lite',
    name: 'AudioFlex Lite',
    category: 'wireless_headphones',
    priceInr: 1999,
    batteryHours: 30,
    ancType: 'Passive Noise Isolation',
    weightGrams: 165,
    rating: 4.3,
    reviewsCount: 650,
    stock: 24,
    imageUrl: 'https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&q=80',
    description: 'Ultra-lightweight on-ear wireless headphones with quick charge (10 mins = 5 hrs) and comfortable memory foam ear cushions.',
    tags: ['wireless', 'headphones', 'lightweight', 'budget', 'casual'],
  },
  prod_ab_active: {
    id: 'prod_ab_active',
    name: 'AeroBuds Active',
    category: 'tws_earbuds',
    priceInr: 2299,
    batteryHours: 36,
    ancType: 'Environmental Noise Cancellation (ENC)',
    weightGrams: 45,
    rating: 4.5,
    reviewsCount: 820,
    stock: 18,
    imageUrl: 'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80',
    description: 'Pocket-sized True Wireless Earbuds with IPX5 sweat resistance, low-latency gaming mode, and 36-hour total battery with case.',
    tags: ['wireless', 'earbuds', 'workout', 'commute', 'budget'],
  },
  prod_sm_elite: {
    id: 'prod_sm_elite',
    name: 'StudioMax Elite',
    category: 'audiophile_headphones',
    priceInr: 4499,
    batteryHours: 60,
    ancType: 'Pro Active Noise Cancellation',
    weightGrams: 280,
    rating: 4.9,
    reviewsCount: 310,
    stock: 5,
    imageUrl: 'https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&q=80',
    description: 'Premium Hi-Res certified studio wireless headphones with titanium 40mm drivers and lossless spatial audio.',
    tags: ['audiophile', 'wireless', 'headphones', 'studio', 'premium', 'high-end'],
  },
};

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
    id: 'addr_blr_office',
    label: 'Searce Office',
    recipient: 'Aditya Joshi',
    street: 'Level 5, Bagmane Tech Park, CV Raman Nagar',
    city: 'Bengaluru',
    state: 'Karnataka',
    pincode: '560093',
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
    const q = (params.query || '').toLowerCase().trim();
    const results = Object.values(CATALOGUE).filter((p) => {
      if (params.category && p.category !== params.category) return false;
      if (params.maxPriceInr && p.priceInr > params.maxPriceInr) return false;
      if (params.minBatteryHours && p.batteryHours < params.minBatteryHours) return false;
      if (params.ancRequired && !p.ancType.toLowerCase().includes('anc')) return false;

      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.tags.some((t) => t.includes(q))
      );
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
