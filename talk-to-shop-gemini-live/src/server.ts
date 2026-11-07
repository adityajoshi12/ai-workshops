import path from 'path';
import { fileURLToPath } from 'url';
import Fastify from 'fastify';
import fastifyStatic from '@fastify/static';
import fastifyWebsocket from '@fastify/websocket';
import dotenv from 'dotenv';
import WebSocket from 'ws';
import { commerce } from './commerce.js';
import { COMMERCE_FUNCTION_DECLARATIONS } from './tools.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const PORT = parseInt(process.env.PORT || '3000', 10);
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const GEMINI_LIVE_MODEL = process.env.GEMINI_LIVE_MODEL || 'gemini-2.5-flash-native-audio-preview-12-2025';
const GEMINI_LIVE_VOICE = process.env.GEMINI_LIVE_VOICE || 'Aoede';

const app = Fastify({ logger: false });

// Register WebSocket support
await app.register(fastifyWebsocket);

// Register static file serving for public UI
await app.register(fastifyStatic, {
  root: path.join(rootDir, 'public'),
  prefix: '/',
});

// ----------------------------------------------------------------------------
// REST API Endpoints
// ----------------------------------------------------------------------------

app.get('/api/health', async () => {
  return {
    status: 'ok',
    hasApiKey: Boolean(GEMINI_API_KEY && GEMINI_API_KEY !== 'your_gemini_api_key_here'),
    model: GEMINI_LIVE_MODEL,
    voice: GEMINI_LIVE_VOICE,
    catalogItems: Object.keys(commerce.searchProducts({}).products).length,
  };
});

app.get('/api/products', async () => {
  return commerce.searchProducts({});
});

app.get('/api/cart', async () => {
  return commerce.getCart();
});

app.post('/api/cart/reset', async () => {
  commerce.reset();
  return { success: true, cart: commerce.getCart() };
});

app.get('/api/addresses', async () => {
  return commerce.getSavedAddresses();
});

// Direct Tool Execution API
app.post('/api/tools/execute', async (request) => {
  const body = request.body as { name: string; args: Record<string, any> };
  const result = executeTool(body.name, body.args || {});
  return { tool: body.name, result, cart: commerce.getCart() };
});

// ----------------------------------------------------------------------------
// Tool Execution Dispatcher (Authoritative Backend)
// ----------------------------------------------------------------------------
function executeTool(name: string, args: Record<string, any>): any {
  switch (name) {
    case 'search_products':
      return commerce.searchProducts({
        query: args.query,
        category: args.category,
        maxPriceInr: args.maxPriceInr,
        minBatteryHours: args.minBatteryHours,
        ancRequired: args.ancRequired,
      });

    case 'get_product_details':
      return commerce.getProductDetails(args.productId);

    case 'compare_products':
      return commerce.compareProducts(args.productIds || []);

    case 'check_inventory':
      return commerce.checkInventory(args.productId, args.pincode);

    case 'add_to_cart':
      return commerce.addToCart(args.productId, args.quantity || 1);

    case 'get_cart':
      return commerce.getCart();

    case 'check_delivery':
      return commerce.checkDelivery(args.pincode || '560103');

    case 'get_saved_addresses':
      return commerce.getSavedAddresses();

    case 'place_order':
      return commerce.placeOrder({
        addressId: args.addressId,
        paymentMethod: args.paymentMethod,
        userConfirmed: Boolean(args.userConfirmed),
      });

    default:
      return { error: `Unknown commerce function: ${name}` };
  }
}

// ----------------------------------------------------------------------------
// WebSocket Proxy: Browser <==> Cloud Run Backend Proxy <==> Gemini Live API
// ----------------------------------------------------------------------------
app.get('/ws/live', { websocket: true }, (connection, req) => {
  const clientWs = connection;
  console.log('[Proxy] Client connected to live audio socket');

  const hasValidKey = Boolean(GEMINI_API_KEY && GEMINI_API_KEY !== 'your_gemini_api_key_here');

  if (!hasValidKey) {
    console.log('[Proxy] Running in SIMULATION MODE (No GEMINI_API_KEY configured).');
    clientWs.send(
      JSON.stringify({
        type: 'status',
        text: 'Simulation Mode: GEMINI_API_KEY not configured. Quick triggers and commerce execution are active.',
        simulation: true,
      })
    );

    clientWs.on('message', (raw) => {
      try {
        const msg = JSON.parse(raw.toString());
        if (msg.type === 'simulate_query') {
          handleSimulatedQuery(clientWs, msg.text);
        }
      } catch (e) {
        // Audio binary chunk ignored in simulation mode
      }
    });
    return;
  }

  // Connect to Google Gemini Live API native WebSocket
  const geminiWsUrl = `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key=${GEMINI_API_KEY}`;
  const geminiWs = new WebSocket(geminiWsUrl);

  geminiWs.on('open', () => {
    console.log('[Proxy] Connected to Gemini Live API WebSocket');
    clientWs.send(JSON.stringify({ type: 'status', text: 'Connected to Gemini Live API', connected: true }));

    // Send initial setup frame
    const setupMsg = {
      setup: {
        model: `models/${GEMINI_LIVE_MODEL}`,
        generationConfig: {
          responseModalities: ['AUDIO'],
          speechConfig: {
            voiceConfig: {
              prebuiltVoiceConfig: {
                voiceName: GEMINI_LIVE_VOICE,
              },
            },
          },
        },
        systemInstruction: {
          parts: [
            {
              text:
                'You are ShopTalk AI, a friendly, concise voice-first shopping assistant. ' +
                'Never invent product prices, stock, or delivery times. Always call the provided commerce functions. ' +
                'Keep verbal answers to 2-3 crisp sentences. Never read out raw URLs. ' +
                'Pronounce prices naturally as full words, for example: "two thousand seven hundred ninety-nine rupees". ' +
                'Before invoking place_order, you MUST read out the items, delivery address, and total in INR and get explicit verbal confirmation.',
            },
          ],
        },
        tools: [
          {
            functionDeclarations: COMMERCE_FUNCTION_DECLARATIONS,
          },
        ],
      },
    };

    geminiWs.send(JSON.stringify(setupMsg));
  });

  // Handle messages from Gemini Live API
  geminiWs.on('message', (data: WebSocket.RawData) => {
    try {
      const response = JSON.parse(data.toString());

      // 1. Interruption notification (Barge-in)
      if (response.serverContent?.interrupted) {
        clientWs.send(JSON.stringify({ type: 'interrupted' }));
      }

      // 2. Incoming audio parts
      const parts = response.serverContent?.modelTurn?.parts;
      if (parts) {
        for (const part of parts) {
          if (part.inlineData?.data) {
            // Forward base64 24kHz PCM to client
            clientWs.send(
              JSON.stringify({
                type: 'audio_chunk',
                mimeType: part.inlineData.mimeType || 'audio/pcm;rate=24000',
                data: part.inlineData.data,
              })
            );
          }
          if (part.text) {
            clientWs.send(JSON.stringify({ type: 'transcript', role: 'assistant', text: part.text }));
          }
        }
      }

      // 3. Tool Calls (Function execution)
      if (response.toolCall?.functionCalls) {
        const functionCalls = response.toolCall.functionCalls;
        const functionResponses = [];

        for (const call of functionCalls) {
          console.log(`[Proxy] Executing tool: ${call.name}(${JSON.stringify(call.args)})`);
          const result = executeTool(call.name, call.args || {});

          // Emit dual-delivery UI event to browser
          clientWs.send(
            JSON.stringify({
              type: 'dual_delivery',
              tool: call.name,
              args: call.args,
              result,
              cart: commerce.getCart(),
            })
          );

          functionResponses.push({
            id: call.id,
            name: call.name,
            response: { output: result },
          });
        }

        // Return tool results back to Gemini Live
        const toolResponseMsg = {
          toolResponse: {
            functionResponses,
          },
        };
        geminiWs.send(JSON.stringify(toolResponseMsg));
      }
    } catch (err) {
      console.error('[Proxy] Error parsing Gemini message:', err);
    }
  });

  // Handle messages from browser client
  clientWs.on('message', (raw) => {
    try {
      const msg = JSON.parse(raw.toString());

      if (msg.type === 'audio_chunk') {
        // Forward client microphone chunk (16kHz PCM base64) to Gemini
        if (geminiWs.readyState === WebSocket.OPEN) {
          const clientChunk = {
            realtimeInput: {
              mediaChunks: [
                {
                  mimeType: 'audio/pcm;rate=16000',
                  data: msg.data,
                },
              ],
            },
          };
          geminiWs.send(JSON.stringify(clientChunk));
        }
      } else if (msg.type === 'text_query') {
        // Optional text input injection for live demo convenience
        if (geminiWs.readyState === WebSocket.OPEN) {
          const textMsg = {
            clientContent: {
              turns: [
                {
                  role: 'user',
                  parts: [{ text: msg.text }],
                },
              ],
              turnComplete: true,
            },
          };
          geminiWs.send(JSON.stringify(textMsg));
        }
      }
    } catch (e) {
      // Binary or invalid JSON
    }
  });

  clientWs.on('close', () => {
    console.log('[Proxy] Client disconnected');
    if (geminiWs.readyState === WebSocket.OPEN) {
      geminiWs.close();
    }
  });

  geminiWs.on('close', () => {
    console.log('[Proxy] Gemini Live API connection closed');
    clientWs.send(JSON.stringify({ type: 'status', text: 'Gemini session closed', connected: false }));
  });

  geminiWs.on('error', (err) => {
    console.error('[Proxy] Gemini WebSocket error:', err);
    clientWs.send(JSON.stringify({ type: 'error', text: err.message }));
  });
});

// ----------------------------------------------------------------------------
// Offline Demonstration / Fallback Simulation Mode
// ----------------------------------------------------------------------------
function handleSimulatedQuery(clientWs: any, query: string) {
  const lower = query.toLowerCase();

  if (lower.includes('search') || lower.includes('travel') || lower.includes('headphones')) {
    const res = commerce.searchProducts({ query: 'travel', maxPriceInr: 3000 });
    clientWs.send(
      JSON.stringify({
        type: 'dual_delivery',
        tool: 'search_products',
        args: { query: 'travel', maxPriceInr: 3000 },
        result: res,
        cart: commerce.getCart(),
        simulatedSpeech:
          'I found two great options under 3,000 rupees for travel: the TravelBeats X with 50-hour battery life for ₹2,799, and the SoundWave Pro for ₹2,499. Would you like me to add one to your cart?',
      })
    );
  } else if (lower.includes('compare')) {
    const res = commerce.compareProducts(['prod_tb_x', 'prod_sw_pro']);
    clientWs.send(
      JSON.stringify({
        type: 'dual_delivery',
        tool: 'compare_products',
        args: { productIds: ['prod_tb_x', 'prod_sw_pro'] },
        result: res,
        cart: commerce.getCart(),
        simulatedSpeech:
          'Comparing both: TravelBeats X has 50 hours of battery life and Hybrid ANC for ₹2,799. SoundWave Pro gives you 40 hours with Adaptive ANC for ₹2,499. For frequent travel, TravelBeats X has 10 extra hours.',
      })
    );
  } else if (lower.includes('add') || lower.includes('cart')) {
    const res = commerce.addToCart('prod_tb_x', 1);
    clientWs.send(
      JSON.stringify({
        type: 'dual_delivery',
        tool: 'add_to_cart',
        args: { productId: 'prod_tb_x', quantity: 1 },
        result: res,
        cart: commerce.getCart(),
        simulatedSpeech:
          'I added the TravelBeats X to your cart. Your subtotal is ₹2,799, plus 18% GST of ₹504, bringing the total to ₹3,303 with free express shipping. Ready to check delivery or place your order?',
      })
    );
  } else if (lower.includes('delivery') || lower.includes('560103')) {
    const res = commerce.checkDelivery('560103');
    clientWs.send(
      JSON.stringify({
        type: 'dual_delivery',
        tool: 'check_delivery',
        args: { pincode: '560103' },
        result: res,
        cart: commerce.getCart(),
        simulatedSpeech:
          'Delivery to Bellandur Bengaluru 560103 is guaranteed tomorrow by 2:00 PM with free express shipping.',
      })
    );
  } else if (lower.includes('confirm') || lower.includes('order')) {
    const res = commerce.placeOrder({ addressId: 'addr_blr_home', userConfirmed: true });
    clientWs.send(
      JSON.stringify({
        type: 'dual_delivery',
        tool: 'place_order',
        args: { userConfirmed: true },
        result: res,
        cart: commerce.getCart(),
        simulatedSpeech: res.message,
      })
    );
  }
}

// ----------------------------------------------------------------------------
// Start Server
// ----------------------------------------------------------------------------
try {
  await app.listen({ port: PORT, host: '0.0.0.0' });
  console.log(`\n===============================================================`);
  console.log(`  ShopTalk AI — Voice E-Commerce Demo Server`);
  console.log(`  URL: http://localhost:${PORT}`);
  console.log(`  WebSocket: ws://localhost:${PORT}/ws/live`);
  console.log(`  Gemini Live Model: ${GEMINI_LIVE_MODEL}`);
  console.log(`  API Key Configured: ${Boolean(GEMINI_API_KEY && GEMINI_API_KEY !== 'your_gemini_api_key_here')}`);
  console.log(`===============================================================\n`);
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
