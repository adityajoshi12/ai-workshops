# Talk to Shop: Voice-First E-Commerce Agent with Gemini Live API

> **Conference Presentation & Live Demo Reference Architecture**  
> Building real-time conversational shopping experiences using the native Gemini Live API, an authoritative Node.js backend proxy, and a synchronized Dual Delivery UI.

---

## 🎯 Architecture Highlights

- **Direct Gemini Live API Integration:** Uses the native speech-to-speech Gemini Live WebSocket protocol via the official `@google/genai` SDK—**no ADK, LangChain, or intermediary framework**.
- **Proxy Server Architecture (Pattern 3):** The browser client connects to our Fastify WebSocket proxy (`ws://localhost:3000/ws/live`). Your `GEMINI_API_KEY` never touches client network traffic.
- **Authoritative Backend Execution:** The model **never** decides prices, modifies stock, or executes transactions directly. Gemini emits structured tool calls; the server validates inventory and updates state.
- **Dual Delivery UX:** Voice guides the customer's ears while product recommendation cards, cart tallies, and delivery lead times update on the screen in real time.
- **Instant Interruption Handling (Barge-in):** Mid-sentence user speech triggers an immediate Web Audio queue flush.
- **Transaction Safety:** Mandatory explicit confirmation before calling `place_order`.

---

## 📂 Project Structure

```
talk-to-shop-gemini-live/
├── src/
│   ├── server.ts        # Fastify WebSocket server & Gemini Live proxy relay
│   ├── commerce.ts      # Authoritative catalog, cart state & order management
│   └── tools.ts         # 9 official Gemini Live tool declarations
├── public/
│   ├── index.html       # Dual Delivery visual shopping interface
│   ├── styles.css       # Clean, modern UI styling
│   └── app.js           # 16kHz audio capture, 24kHz playback queue, event handling
├── .env.example         # Environment template for GEMINI_API_KEY
├── package.json         # Node.js project configuration
├── tsconfig.json        # TypeScript configuration
└── README.md            # Complete documentation & demo runbook
```

---

## ⚡ Quickstart

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and add your Google AI Studio API key:
```env
GEMINI_API_KEY=AIzaSy...
PORT=3000
GEMINI_LIVE_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
GEMINI_LIVE_VOICE=Aoede
```
*(Note: If you run without a `GEMINI_API_KEY`, the application automatically launches in **Simulation Mode**, allowing you to test all commerce tools and the Dual Delivery UI with simulated voice and 1-click demo triggers!)*

### 3. Run the Application
```bash
npm run dev
```

Open your browser at:
👉 **`http://localhost:3000`**

---

## 🎙️ Live Demo Script (6–8 Minutes)

| Step | What to Say / Trigger | What Gemini & The Backend Do | What Appears on Screen (Dual Delivery) |
|---|---|---|---|
| **1. Discovery** | *"I need travel headphones under ₹3,000 with long battery."* | Gemini triggers `search_products({ query: "travel", maxPriceInr: 3000 })`. Backend filters catalog. | Product cards for **TravelBeats X** (₹2,799, 50h) and **SoundWave Pro** (₹2,499, 40h) slide onto the screen. |
| **2. Comparison** | *"Compare TravelBeats X with SoundWave Pro."* | Gemini calls `compare_products(["prod_tb_x", "prod_sw_pro"])`. | Comparison highlights battery and ANC differences. |
| **3. Cart Addition** | *"Add TravelBeats X to my cart."* | Backend validates stock (8 units), adds item, calculates 18% GST (₹504) and total (₹3,303). | Cart drawer opens, items and subtotal update instantly. |
| **4. Delivery Check** | *"Check delivery to 560103."* | Backend checks warehouse hub logistics. | Pincode badge shows *"Guaranteed Next-Day Delivery by 2:00 PM"*. |
| **5. Safe Checkout** | *"Place the order."* &rarr; Gemini reads back total & asks for confirmation &rarr; *"Yes, confirm!"* | Backend verifies `userConfirmed: true`, generates Order ID, clears cart, deducts stock. | **Order Confirmed** modal pops up with tracking number and delivery details! |

---

## 🛠️ The 9 Authoritative Commerce Tools

1. `search_products(query, category, maxPriceInr, minBatteryHours, ancRequired)`
2. `get_product_details(productId)`
3. `compare_products(productIds)`
4. `check_inventory(productId, pincode)`
5. `add_to_cart(productId, quantity)`
6. `get_cart()`
7. `check_delivery(pincode)`
8. `get_saved_addresses()`
9. `place_order(addressId, paymentMethod, userConfirmed)`

---

## 🚀 Cloud Run Deployment

To deploy this backend proxy to Google Cloud Run:

```bash
# Build & Deploy directly to Cloud Run
gcloud run deploy talk-to-shop \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY="your-secret-key"
```

Cloud Run supports WebSockets out of the box with up to 60-minute connection timeouts!
