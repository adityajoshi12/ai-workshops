/**
 * Seeded Authoritative Product Catalogue
 *
 * Pure data: no business logic lives here. To add a category, just add products;
 * the `category` enum exposed to Gemini (tools.ts) is derived from this file.
 */
import type { Product } from './commerce.js';

// Generated placeholder art (no network, never 404s). Swap `imageUrl` for real photos any time.
const CATEGORY_ART: Record<string, [emoji: string, from: string, to: string]> = {
  smartphones: ['📱', '#4f46e5', '#7c3aed'],
  laptops: ['💻', '#0f766e', '#0891b2'],
  smartwatches: ['⌚', '#be185d', '#e11d48'],
  bluetooth_speakers: ['🔊', '#b45309', '#ea580c'],
  tablets: ['📲', '#1d4ed8', '#0ea5e9'],
  cameras: ['📷', '#334155', '#64748b'],
  gaming_accessories: ['🎮', '#6d28d9', '#c026d3'],
  power_banks: ['🔋', '#15803d', '#65a30d'],
  smart_home: ['🏠', '#0369a1', '#14b8a6'],
};

function artFor(category: string): string {
  const [emoji, from, to] = CATEGORY_ART[category];
  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' width='500' height='375'>` +
    `<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>` +
    `<stop offset='0' stop-color='${from}'/><stop offset='1' stop-color='${to}'/></linearGradient></defs>` +
    `<rect width='500' height='375' fill='url(#g)'/>` +
    `<text x='250' y='215' font-size='140' text-anchor='middle'>${emoji}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

type NewProduct = Omit<Product, 'imageUrl'>;

/** Builds a catalogue entry and attaches the category art. */
function item(p: NewProduct): [string, Product] {
  return [p.id, { ...p, imageUrl: artFor(p.category) }];
}

// Original audio range (real photos).
const AUDIO_CATALOGUE: Record<string, Product> = {
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

// Wider electronics range.
const ELECTRONICS: NewProduct[] = [
  // --- Smartphones ---
  {
    id: 'prod_ph_nova_x5', name: 'Nova X5 5G', category: 'smartphones', priceInr: 17999,
    batteryHours: 22, weightGrams: 188, rating: 4.4, reviewsCount: 2310, stock: 12,
    description: 'Mid-range 5G phone with a bright 120Hz AMOLED display, 50MP OIS camera and 33W fast charging.',
    tags: ['smartphone', 'phone', '5g', 'camera', 'midrange', 'amoled'],
    highlights: ['6.67" AMOLED 120Hz', '8GB + 128GB', '50MP OIS camera'],
  },
  {
    id: 'prod_ph_pulse_ultra', name: 'Pulse Ultra 5G', category: 'smartphones', priceInr: 54999,
    batteryHours: 26, weightGrams: 219, rating: 4.8, reviewsCount: 870, stock: 6,
    description: 'Flagship phone with a 200MP main camera, 5x periscope zoom and a vapour-cooled chip for sustained gaming.',
    tags: ['smartphone', 'phone', '5g', 'flagship', 'camera', 'gaming', 'premium'],
    highlights: ['6.8" LTPO OLED', '12GB + 256GB', '200MP + 5x zoom'],
  },
  {
    id: 'prod_ph_lume_a15', name: 'Lume A15', category: 'smartphones', priceInr: 9499,
    batteryHours: 34, weightGrams: 195, rating: 4.1, reviewsCount: 5120, stock: 30,
    description: 'Entry-level phone built around a 5000mAh battery that easily lasts two days of normal use.',
    tags: ['smartphone', 'phone', 'budget', 'long-battery', 'entry'],
    highlights: ['6.6" HD+ 90Hz', '4GB + 64GB', '5000mAh battery'],
  },
  // --- Laptops ---
  {
    id: 'prod_lp_aerobook_14', name: 'AeroBook Air 14', category: 'laptops', priceInr: 64990,
    batteryHours: 15, weightGrams: 1240, rating: 4.7, reviewsCount: 640, stock: 9,
    description: 'Thin and light 14-inch ultrabook with a sharp OLED panel, built for students and travelling professionals.',
    tags: ['laptop', 'ultrabook', 'work', 'student', 'lightweight', 'travel', 'oled'],
    highlights: ['14" 2.8K OLED', '16GB RAM + 512GB SSD', '8-core processor'],
  },
  {
    id: 'prod_lp_forgebook_g16', name: 'ForgeBook G16', category: 'laptops', priceInr: 89990,
    batteryHours: 6, weightGrams: 2350, rating: 4.6, reviewsCount: 410, stock: 4,
    description: 'Gaming laptop with a dedicated RTX 4060 GPU, a 165Hz QHD display and a vapour-chamber cooling system.',
    tags: ['laptop', 'gaming', 'rtx', 'high-performance', 'creator'],
    highlights: ['16" 165Hz QHD', 'RTX 4060 8GB', '16GB RAM + 1TB SSD'],
  },
  // --- Smartwatches ---
  {
    id: 'prod_wt_pulsefit_3', name: 'PulseFit Band 3', category: 'smartwatches', priceInr: 3499,
    batteryHours: 336, weightGrams: 28, rating: 4.3, reviewsCount: 3890, stock: 40,
    description: 'Slim fitness band with an AMOLED screen, 24x7 heart rate and SpO2 tracking, and a 14-day battery.',
    tags: ['smartwatch', 'watch', 'band', 'fitness', 'budget', 'long-battery', 'workout'],
    highlights: ['1.7" AMOLED', 'Heart rate + SpO2', '5ATM water resistant'],
  },
  {
    id: 'prod_wt_chronox_active', name: 'ChronoX Active Watch', category: 'smartwatches', priceInr: 12999,
    batteryHours: 96, weightGrams: 48, rating: 4.6, reviewsCount: 1260, stock: 15,
    description: 'Premium sports smartwatch with dual-band GPS, ECG, sleep coaching and a sapphire-glass dial.',
    tags: ['smartwatch', 'watch', 'gps', 'fitness', 'running', 'premium', 'ecg'],
    highlights: ['1.4" AMOLED', 'Dual-band GPS', 'ECG + sleep tracking'],
  },
  // --- Bluetooth speakers ---
  {
    id: 'prod_sp_boombox_mini', name: 'BoomBox Mini', category: 'bluetooth_speakers', priceInr: 2999,
    batteryHours: 12, weightGrams: 540, rating: 4.5, reviewsCount: 2750, stock: 22,
    description: 'Rugged pocket-friendly speaker with punchy stereo sound that survives rain, dust and pool splashes.',
    tags: ['speaker', 'bluetooth', 'portable', 'waterproof', 'outdoor', 'budget'],
    highlights: ['IP67 waterproof', '20W stereo', 'Pair two for party mode'],
  },
  {
    id: 'prod_sp_thunderpod_120', name: 'ThunderPod 120', category: 'bluetooth_speakers', priceInr: 8999,
    batteryHours: 18, weightGrams: 3800, rating: 4.4, reviewsCount: 530, stock: 7,
    description: 'Big party speaker with deep bass, wired-mic karaoke input and reactive LED lighting.',
    tags: ['speaker', 'bluetooth', 'party', 'karaoke', 'bass', 'high-power'],
    highlights: ['120W output', 'Karaoke mic input', 'Reactive LED lights'],
  },
  // --- Tablets ---
  {
    id: 'prod_tab_slate_11', name: 'SlateTab 11', category: 'tablets', priceInr: 24999,
    batteryHours: 12, weightGrams: 480, rating: 4.5, reviewsCount: 980, stock: 11,
    description: 'Eleven-inch tablet with a crisp 2K display, quad speakers and stylus support for notes and sketching.',
    tags: ['tablet', 'study', 'drawing', 'entertainment', 'stylus', 'student'],
    highlights: ['11" 2K 90Hz', '8GB + 128GB', 'Stylus support'],
  },
  // --- Cameras ---
  {
    id: 'prod_cam_trailgo_4k', name: 'TrailCam Go 4K', category: 'cameras', priceInr: 14999,
    batteryHours: 2.5, weightGrams: 120, rating: 4.5, reviewsCount: 720, stock: 10,
    description: 'Compact action camera that shoots stabilised 4K at 60fps and is waterproof to ten metres without a case.',
    tags: ['camera', 'action', 'vlog', 'travel', '4k', 'waterproof', 'adventure'],
    highlights: ['4K 60fps', 'Waterproof to 10m', 'EIS stabilisation'],
  },
  // --- Gaming accessories ---
  {
    id: 'prod_gm_vortex_pad', name: 'Vortex Pro Controller', category: 'gaming_accessories', priceInr: 3299,
    batteryHours: 30, weightGrams: 260, rating: 4.6, reviewsCount: 1840, stock: 20,
    description: 'Wireless gamepad for PC, phone and console with drift-free Hall-effect sticks and remappable back paddles.',
    tags: ['gaming', 'controller', 'gamepad', 'wireless', 'pc', 'mobile'],
    highlights: ['Hall-effect sticks', 'Bluetooth + 2.4GHz', 'Remappable back paddles'],
  },
  {
    id: 'prod_gm_keyforge_75', name: 'KeyForge 75 Keyboard', category: 'gaming_accessories', priceInr: 4999,
    batteryHours: 80, weightGrams: 780, rating: 4.7, reviewsCount: 690, stock: 2,
    description: 'Compact 75% mechanical keyboard with hot-swappable switches, gasket mount and per-key RGB.',
    tags: ['gaming', 'keyboard', 'mechanical', 'wireless', 'rgb', 'work'],
    highlights: ['Hot-swappable switches', 'Tri-mode wireless', 'Per-key RGB'],
  },
  // --- Power banks (mains/passive: no batteryHours) ---
  {
    id: 'prod_pb_voltmax_20k', name: 'VoltMax 20000', category: 'power_banks', priceInr: 2199,
    weightGrams: 430, rating: 4.4, reviewsCount: 4300, stock: 35,
    description: 'High-capacity power bank with 65W USB-C Power Delivery, enough to charge a laptop or a phone several times.',
    tags: ['powerbank', 'power bank', 'charger', 'travel', 'fast-charging', 'usb-c', 'budget'],
    highlights: ['20,000 mAh', '65W USB-C PD', 'Charges laptops'],
  },
  // --- Smart home ---
  {
    id: 'prod_sh_homeeye_360', name: 'HomeEye 360 Camera', category: 'smart_home', priceInr: 2499,
    weightGrams: 250, rating: 4.3, reviewsCount: 3120, stock: 25,
    description: 'Indoor pan-tilt security camera with 2K video, colour night vision, motion alerts and two-way talk.',
    tags: ['smart home', 'camera', 'security', 'cctv', 'indoor', 'budget', 'monitoring'],
    highlights: ['2K pan-tilt', 'Colour night vision', 'Two-way talk'],
  },
];

export const CATALOGUE: Record<string, Product> = {
  ...AUDIO_CATALOGUE,
  ...Object.fromEntries(ELECTRONICS.map(item)),
};
