/**
 * ShopTalk AI — Client Audio & Dual Delivery UI Controller
 */

(function () {
  let ws = null;
  let audioCtx = null;
  let micStream = null;
  let scriptProcessor = null;
  let isRecording = false;
  let isSimulated = false;

  // Audio Playback Queue (24kHz PCM from Gemini)
  let audioQueue = [];
  let isPlaying = false;
  let currentAudioSource = null;

  // DOM Elements
  const connectionPill = document.getElementById('connection-pill');
  const statusText = document.getElementById('status-text');
  const micBtn = document.getElementById('mic-toggle-btn');
  const visualizer = document.getElementById('visualizer-bars');
  const voiceHeading = document.getElementById('voice-heading');
  const voiceSubheading = document.getElementById('voice-subheading');
  const productGrid = document.getElementById('product-grid');
  const productCountBadge = document.getElementById('product-count-badge');
  const cartList = document.getElementById('cart-items-list');
  const cartItemCount = document.getElementById('cart-item-count');
  const cartSummary = document.getElementById('cart-summary');
  const subtotalVal = document.getElementById('subtotal-val');
  const gstVal = document.getElementById('gst-val');
  const totalVal = document.getElementById('total-val');
  const resetBtn = document.getElementById('reset-cart-btn');
  const checkoutBtn = document.getElementById('checkout-btn');
  const telemetryLog = document.getElementById('telemetry-log');
  const orderModal = document.getElementById('order-modal');
  const modalOrderId = document.getElementById('modal-order-id');
  const modalOrderMsg = document.getElementById('modal-order-msg');
  const closeModalBtn = document.getElementById('close-modal-btn');
  const triggerPills = document.querySelectorAll('.trigger-pill');

  function logTelemetry(type, msg) {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    div.innerHTML = `<span class="time">[${time}]</span> ${msg}`;
    telemetryLog.appendChild(div);
    telemetryLog.scrollTop = telemetryLog.scrollHeight;
  }

  // --------------------------------------------------------------------------
  // WebSocket Connection & Event Relay
  // --------------------------------------------------------------------------
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      connectionPill.className = 'status-pill online';
      statusText.textContent = 'Live Audio Connected';
      logTelemetry('system', 'WebSocket connection established with Cloud Run Proxy.');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'status') {
          if (msg.simulation) {
            isSimulated = true;
            statusText.textContent = 'Simulation Mode';
            logTelemetry('system', msg.text);
          } else {
            statusText.textContent = msg.text;
            logTelemetry('system', msg.text);
          }
        } else if (msg.type === 'interrupted') {
          logTelemetry('interrupted', '⚡ Barge-in detected: Gemini interrupted by user audio! Flushing playback buffer.');
          flushAudioQueue();
        } else if (msg.type === 'audio_chunk') {
          playPcm24kChunk(msg.data);
        } else if (msg.type === 'transcript') {
          logTelemetry('assistant', `<strong>Gemini:</strong> ${msg.text}`);
        } else if (msg.type === 'dual_delivery') {
          handleDualDeliveryEvent(msg);
        }
      } catch (e) {
        console.error('Error parsing WS message:', e);
      }
    };

    ws.onclose = () => {
      connectionPill.className = 'status-pill offline';
      statusText.textContent = 'Disconnected';
      logTelemetry('system', 'WebSocket connection closed. Retrying in 3s...');
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error('WS Error:', err);
    };
  }

  // --------------------------------------------------------------------------
  // Dual Delivery UI Handler
  // --------------------------------------------------------------------------
  function handleDualDeliveryEvent(msg) {
    logTelemetry('tool', `⚙️ Tool Executed: <strong>${msg.tool}</strong>(${JSON.stringify(msg.args || {})})`);

    // 1. Update Products Shelf
    if (msg.tool === 'search_products' || msg.tool === 'compare_products') {
      const products = msg.result.products || msg.result.compared || [];
      renderProducts(products);
    }

    // 2. Update Cart State
    if (msg.cart) {
      renderCart(msg.cart);
    }

    // 3. Handle Order Confirmation
    if (msg.tool === 'place_order' && msg.result?.success) {
      modalOrderId.textContent = msg.result.order.orderId;
      modalOrderMsg.textContent = msg.result.message;
      orderModal.classList.add('open');
      renderCart(msg.cart);
    }

    // 4. Handle Simulated Speech
    if (msg.simulatedSpeech) {
      logTelemetry('assistant', `<strong>ShopTalk AI:</strong> ${msg.simulatedSpeech}`);
      speakTextSynthetic(msg.simulatedSpeech);
    }
  }

  function renderProducts(products) {
    productCountBadge.textContent = `${products.length} items`;
    if (!products || products.length === 0) {
      productGrid.innerHTML = `
        <div class="empty-shelf">
          <p>No products matched your exact search query. Try broadening your price or battery criteria.</p>
        </div>`;
      return;
    }

    productGrid.innerHTML = products
      .map(
        (p) => `
      <div class="product-card" data-id="${p.id}">
        <div class="card-img-wrap">
          <img class="card-img" src="${p.imageUrl}" alt="${p.name}">
          <span class="stock-tag">✓ In Stock (${p.stock})</span>
        </div>
        <div class="card-body">
          <h4 class="product-title">${p.name}</h4>
          <p class="product-desc">${p.description}</p>
          <div class="specs-row">
            <span class="spec-pill">🔋 ${p.batteryHours}h Battery</span>
            <span class="spec-pill">🎧 ${p.ancType}</span>
            <span class="spec-pill">⭐ ${p.rating} (${p.reviewsCount})</span>
          </div>
          <div class="card-footer">
            <span class="price-tag">₹${p.priceInr.toLocaleString('en-IN')}</span>
            <button class="add-btn" onclick="window.ShopTalk.addToCart('${p.id}')">+ Add to Cart</button>
          </div>
        </div>
      </div>
    `
      )
      .join('');
  }

  function renderCart(cart) {
    cartItemCount.textContent = `${cart.itemCount} items`;

    if (!cart.items || cart.items.length === 0) {
      cartList.innerHTML = `<p class="empty-text">Your cart is empty.</p>`;
      cartSummary.style.display = 'none';
      return;
    }

    cartList.innerHTML = cart.items
      .map(
        (item) => `
      <div class="cart-item-row">
        <div>
          <span class="cart-item-name">${item.product.name}</span>
          <span class="cart-item-qty">x${item.quantity}</span>
        </div>
        <span class="cart-item-price">₹${item.itemSubtotalInr.toLocaleString('en-IN')}</span>
      </div>
    `
      )
      .join('');

    subtotalVal.textContent = `₹${cart.subtotalInr.toLocaleString('en-IN')}`;
    gstVal.textContent = `₹${cart.gstInr.toLocaleString('en-IN')}`;
    totalVal.textContent = `₹${cart.totalInr.toLocaleString('en-IN')}`;
    cartSummary.style.display = 'flex';
  }

  // --------------------------------------------------------------------------
  // Web Audio PCM Playback (24kHz from Gemini Live)
  // --------------------------------------------------------------------------
  function ensureAudioContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
  }

  function playPcm24kChunk(base64Data) {
    ensureAudioContext();
    const binary = atob(base64Data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0;
    }

    const buffer = audioCtx.createBuffer(1, float32.length, 24000);
    buffer.copyToChannel(float32, 0);

    audioQueue.push(buffer);
    if (!isPlaying) {
      playNextInQueue();
    }
  }

  function playNextInQueue() {
    if (audioQueue.length === 0) {
      isPlaying = false;
      return;
    }
    isPlaying = true;
    const buffer = audioQueue.shift();
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    currentAudioSource = source;

    source.onended = () => {
      currentAudioSource = null;
      playNextInQueue();
    };
    source.start();
  }

  function flushAudioQueue() {
    if (currentAudioSource) {
      try {
        currentAudioSource.stop();
      } catch (e) {}
      currentAudioSource = null;
    }
    audioQueue = [];
    isPlaying = false;
  }

  // --------------------------------------------------------------------------
  // Microphone Stream Capture (16kHz PCM to Gemini Live)
  // --------------------------------------------------------------------------
  async function startRecording() {
    ensureAudioContext();
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const source = audioCtx.createMediaStreamSource(micStream);
      scriptProcessor = audioCtx.createScriptProcessor(2048, 1, 1);

      scriptProcessor.onaudioprocess = (e) => {
        if (!isRecording) return;
        const inputData = e.inputBuffer.getChannelData(0);

        // Convert Float32 to Int16 PCM
        const int16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        // Base64 encode
        let binary = '';
        const bytes = new Uint8Array(int16.buffer);
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const b64 = btoa(binary);

        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'audio_chunk', data: b64 }));
        }
      };

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioCtx.destination);

      isRecording = true;
      micBtn.classList.add('active');
      visualizer.classList.add('active');
      voiceHeading.textContent = 'Listening to you...';
      voiceSubheading.textContent = 'Speak naturally, e.g. "Add TravelBeats X to cart"';
      logTelemetry('user', 'Microphone active. Streaming 16kHz PCM audio to Gemini.');
    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('Could not access microphone. Please ensure microphone permissions are granted.');
    }
  }

  function stopRecording() {
    isRecording = false;
    micBtn.classList.remove('active');
    visualizer.classList.remove('active');
    voiceHeading.textContent = 'Tap Mic to Start Talking';
    voiceSubheading.textContent = 'Or use the 1-click Demo Triggers below';

    if (scriptProcessor) {
      scriptProcessor.disconnect();
      scriptProcessor = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
    }
    logTelemetry('user', 'Microphone stopped.');
  }

  function speakTextSynthetic(text) {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  }

  // --------------------------------------------------------------------------
  // Event Bindings
  // --------------------------------------------------------------------------
  micBtn.addEventListener('click', () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  resetBtn.addEventListener('click', async () => {
    await fetch('/api/cart/reset', { method: 'POST' });
    renderCart({ items: [], itemCount: 0, subtotalInr: 0, gstInr: 0, shippingInr: 0, totalInr: 0 });
    productGrid.innerHTML = `
      <div class="empty-shelf">
        <p>Catalogue reset. Start speaking or click a demo trigger above.</p>
      </div>`;
    productCountBadge.textContent = '0 items';
    logTelemetry('system', 'Demo state reset by presenter.');
  });

  checkoutBtn.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'text_query', text: 'Yes, please confirm and place my order.' }));
      logTelemetry('user', 'Clicked "Place Order" — Sent explicit confirmation trigger.');
    }
  });

  closeModalBtn.addEventListener('click', () => {
    orderModal.classList.remove('open');
  });

  triggerPills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const query = pill.getAttribute('data-query');
      logTelemetry('user', `Triggered: "${query}"`);

      if (ws && ws.readyState === WebSocket.OPEN) {
        if (isSimulated) {
          ws.send(JSON.stringify({ type: 'simulate_query', text: query }));
        } else {
          ws.send(JSON.stringify({ type: 'text_query', text: query }));
        }
      }
    });
  });

  // Global helper for Add to Cart button on cards
  window.ShopTalk = {
    addToCart: (productId) => {
      logTelemetry('user', `Direct UI action: Add ${productId} to cart`);
      fetch('/api/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'add_to_cart', args: { productId, quantity: 1 } }),
      })
        .then((r) => r.json())
        .then((data) => {
          renderCart(data.cart);
          logTelemetry('tool', `Authoritative Backend: ${data.result.message}`);
        });
    },
  };

  // Initial Boot
  connectWebSocket();
})();
