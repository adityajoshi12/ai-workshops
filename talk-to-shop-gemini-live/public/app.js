/**
 * ShopTalk AI — Client Audio & Dual Delivery UI Controller
 */

(function () {
  let ws = null;
  let audioCtx = null;
  let micStream = null;
  let scriptProcessor = null;
  let speechRecognizer = null;
  let isRecording = false;
  let isSimulated = false;

  // Real-Time Audio Frequency & Signal Strength Analyser
  let analyserNode = null;
  let frequencyData = null;
  let timeDomainData = null;
  let currentSourceType = 'idle'; // 'mic' | 'ai' | 'ai_synthetic' | 'idle'
  let peakLevel = 0;

  // Audio Playback Queue (24kHz PCM from Gemini)
  let audioQueue = [];
  let isPlaying = false;
  let currentAudioSource = null;

  // DOM Elements
  const connectionPill = document.getElementById('connection-pill');
  const statusText = document.getElementById('status-text');
  const micBtn = document.getElementById('mic-toggle-btn');
  const visualizer = document.getElementById('audio-frequency-hud') || document.getElementById('visualizer-bars');
  const voiceHeading = document.getElementById('voice-heading');
  const voiceSubheading = document.getElementById('voice-subheading');
  const textQueryForm = document.getElementById('text-query-form');
  const textQueryInput = document.getElementById('text-query-input');
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

  // Microphone & Insecure Context Modal Elements
  const micHelpModal = document.getElementById('mic-help-modal');
  const micModalTitle = document.getElementById('mic-modal-title');
  const micModalBody = document.getElementById('mic-modal-body');
  const closeMicModalBtn = document.getElementById('close-mic-modal-btn');
  const insecureBanner = document.getElementById('insecure-context-banner');
  const bannerHelpBtn = document.getElementById('banner-help-btn');

  function showMicHelpModal(title, htmlContent) {
    if (micModalTitle && micModalBody && micHelpModal) {
      micModalTitle.textContent = title;
      micModalBody.innerHTML = htmlContent;
      micHelpModal.classList.add('open');
    } else {
      alert(title + '\n\n' + htmlContent.replace(/<[^>]+>/g, ''));
    }
  }

  function showInsecureHelp() {
    showMicHelpModal(
      'HTTPS Required on iPad & Mobile',
      `<p>You are accessing the workshop at <strong>http://${window.location.host}</strong>.</p>
       <p style="margin-top:8px">Apple (iOS/iPadOS Safari) and Google (Android Chrome) strictly block microphone access on insecure <code>http://</code> network addresses, even when microphone permissions are toggled ON in device settings.</p>
       <div class="code-step">
         <strong>To enable microphone recording on your iPad/phone:</strong>
         <p style="margin-top:6px;font-size:13px">Run this command on your computer to get an instant HTTPS link:</p>
         <pre><code>npm run tunnel</code></pre>
         <span style="font-size:12px;color:var(--text-sub)">Or: <code>cloudflared tunnel --url http://localhost:3000</code></span>
       </div>
       <p style="margin-top:10px">Open the resulting <code>https://...</code> link on your iPad or phone. Microphone permissions will be accepted immediately!</p>`
    );
  }

  function checkInsecureContext() {
    const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
    const isHttps = window.location.protocol === 'https:';
    const isSecure = window.isSecureContext && (isHttps || isLocalhost);

    if (!isSecure && !isLocalhost && insecureBanner) {
      insecureBanner.style.display = 'flex';
      logTelemetry(
        'system',
        '⚠️ Connected over insecure HTTP (' + window.location.host + '). iOS Safari and mobile browsers require HTTPS for microphone capture.'
      );
    }
  }

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
  // Web Audio PCM Playback & Real-Time Frequency Analyser
  // --------------------------------------------------------------------------
  function ensureAudioContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    getAnalyser();
  }

  function getAnalyser() {
    if (!audioCtx) return null;
    if (!analyserNode) {
      analyserNode = audioCtx.createAnalyser();
      analyserNode.fftSize = 64; // 32 frequency bins
      analyserNode.smoothingTimeConstant = 0.8;
      frequencyData = new Uint8Array(analyserNode.frequencyBinCount);
      timeDomainData = new Uint8Array(analyserNode.fftSize);
    }
    return analyserNode;
  }

  // --------------------------------------------------------------------------
  // Real-Time Audio Frequency Spectrum & Signal Strength HUD Renderer
  // --------------------------------------------------------------------------
  function renderAudioHud() {
    const canvas = document.getElementById('frequency-canvas');
    if (!canvas) {
      requestAnimationFrame(renderAudioHud);
      return;
    }

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    let rms = 0;
    if (analyserNode && (currentSourceType === 'mic' || currentSourceType === 'ai')) {
      analyserNode.getByteFrequencyData(frequencyData);
      analyserNode.getByteTimeDomainData(timeDomainData);

      let sum = 0;
      for (let i = 0; i < timeDomainData.length; i++) {
        const v = (timeDomainData[i] - 128) / 128;
        sum += v * v;
      }
      rms = Math.sqrt(sum / timeDomainData.length);
    } else if (currentSourceType === 'ai_synthetic') {
      const t = Date.now() / 120;
      rms = 0.22 + 0.12 * Math.sin(t * 2.5);
      if (frequencyData) {
        for (let i = 0; i < frequencyData.length; i++) {
          const wave = Math.sin(t + i * 0.5) * Math.cos(t * 0.7 + i * 0.2);
          frequencyData[i] = Math.max(15, Math.floor(190 * Math.abs(wave)));
        }
      }
    } else {
      // Smooth idle decay to flatline
      if (frequencyData) {
        for (let i = 0; i < frequencyData.length; i++) {
          frequencyData[i] = Math.max(0, frequencyData[i] * 0.82);
        }
      }
      rms = 0;
    }

    // Convert RMS to decibels (-60 dB to 0 dB) and VU percentage
    let dbText = '-60 dB';
    let percent = 0;
    if (currentSourceType !== 'idle') {
      const rawDb = rms > 0.001 ? 20 * Math.log10(rms) : -60;
      const clampedDb = Math.max(-60, Math.min(0, Math.round(rawDb)));
      dbText = `${clampedDb} dB`;
      percent = Math.min(100, Math.max(0, Math.round(((clampedDb + 60) / 60) * 100)));
    }

    // Peak needle hold & decay
    if (percent > peakLevel) {
      peakLevel = percent;
    } else {
      peakLevel = Math.max(0, peakLevel - 1.4);
    }

    // Update DOM Indicators
    const dbEl = document.getElementById('hud-db-value');
    const barEl = document.getElementById('hud-meter-bar');
    const peakEl = document.getElementById('hud-meter-peak');
    const dotEl = document.getElementById('hud-status-dot');
    const badgeEl = document.getElementById('hud-source-badge');

    if (dbEl) dbEl.textContent = dbText;
    if (barEl) barEl.style.width = `${percent}%`;
    if (peakEl) peakEl.style.left = `${Math.min(99, peakLevel)}%`;

    if (dotEl && badgeEl) {
      if (currentSourceType === 'mic') {
        dotEl.className = 'hud-status-dot live-mic';
        badgeEl.textContent = 'MIC LIVE';
        badgeEl.className = 'hud-source-badge live-mic';
      } else if (currentSourceType === 'ai' || currentSourceType === 'ai_synthetic') {
        dotEl.className = 'hud-status-dot live-ai';
        badgeEl.textContent = 'AI AUDIO';
        badgeEl.className = 'hud-source-badge live-ai';
      } else {
        dotEl.className = 'hud-status-dot';
        badgeEl.textContent = 'IDLE';
        badgeEl.className = 'hud-source-badge';
      }
    }

    // Clear Canvas
    ctx.fillStyle = '#202124';
    ctx.fillRect(0, 0, width, height);

    // Subtle decibel reference grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, Math.floor(height * 0.35));
    ctx.lineTo(width, Math.floor(height * 0.35));
    ctx.moveTo(0, Math.floor(height * 0.7));
    ctx.lineTo(width, Math.floor(height * 0.7));
    ctx.stroke();

    // Draw 24 Frequency Spectrum Bars
    const numBars = 24;
    const barSpacing = 3;
    const totalSpacing = barSpacing * (numBars - 1);
    const barWidth = (width - totalSpacing) / numBars;

    const gradient = ctx.createLinearGradient(0, height, 0, 0);
    if (currentSourceType === 'mic') {
      gradient.addColorStop(0, '#1A73E8');
      gradient.addColorStop(0.5, '#34A853');
      gradient.addColorStop(0.85, '#FBBC05');
      gradient.addColorStop(1, '#EA4335');
    } else if (currentSourceType === 'ai' || currentSourceType === 'ai_synthetic') {
      gradient.addColorStop(0, '#1A73E8');
      gradient.addColorStop(0.6, '#A142F4');
      gradient.addColorStop(1, '#FA7B17');
    } else {
      gradient.addColorStop(0, '#3C4043');
      gradient.addColorStop(1, '#5F6368');
    }

    for (let i = 0; i < numBars; i++) {
      const binIdx = Math.floor((i / numBars) * (frequencyData ? frequencyData.length : 32));
      const val = frequencyData ? frequencyData[binIdx] || 0 : 0;
      const barHeight = Math.max(3, (val / 255) * (height - 4));
      const x = i * (barWidth + barSpacing);
      const y = height - barHeight;

      ctx.fillStyle = gradient;
      ctx.beginPath();
      const r = Math.min(barWidth / 2, 2);
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + barWidth - r, y);
      ctx.quadraticCurveTo(x + barWidth, y, x + barWidth, y + r);
      ctx.lineTo(x + barWidth, height);
      ctx.lineTo(x, height);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
      ctx.fill();
    }

    requestAnimationFrame(renderAudioHud);
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
      if (!isRecording) currentSourceType = 'idle';
      return;
    }
    isPlaying = true;
    currentSourceType = 'ai';
    const buffer = audioQueue.shift();
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);

    const analyser = getAnalyser();
    if (analyser) {
      source.connect(analyser);
    }
    currentAudioSource = source;

    source.onended = () => {
      currentAudioSource = null;
      if (audioQueue.length === 0 && !isRecording) {
        currentSourceType = 'idle';
      }
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
    if (!isRecording) currentSourceType = 'idle';
  }

  // --------------------------------------------------------------------------
  // Microphone Stream Capture & Universal 16kHz Resampling
  // --------------------------------------------------------------------------
  function resampleAudioTo16k(inputData, fromSampleRate) {
    if (!fromSampleRate || fromSampleRate === 16000) {
      const int16 = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      return int16;
    }

    const ratio = fromSampleRate / 16000;
    const outputLength = Math.round(inputData.length / ratio);
    const int16 = new Int16Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const srcIndex = Math.min(Math.round(i * ratio), inputData.length - 1);
      const s = Math.max(-1, Math.min(1, inputData[srcIndex]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return int16;
  }

  async function startRecording() {
    ensureAudioContext();

    // 1. Guard against Insecure Context on mobile
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showInsecureHelp();
      return;
    }

    // 2. In Simulation Mode, initialize browser speech-to-text recognition if available
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (isSimulated && SpeechRec) {
      try {
        speechRecognizer = new SpeechRec();
        speechRecognizer.continuous = true;
        speechRecognizer.interimResults = true;
        speechRecognizer.lang = 'en-US';

        speechRecognizer.onresult = (event) => {
          let interim = '';
          let final = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              final += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          if (interim) {
            voiceHeading.textContent = `"${interim}"`;
          }
          if (final && final.trim()) {
            const query = final.trim();
            voiceHeading.textContent = `"${query}"`;
            logTelemetry('user', `Spoken query: "${query}"`);
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'simulate_query', text: query }));
            }
          }
        };

        speechRecognizer.onerror = (e) => {
          console.warn('Speech recognition warning:', e.error);
        };

        speechRecognizer.start();
      } catch (err) {
        console.warn('Could not start speech recognition:', err);
      }
    }

    try {
      // 3. Request microphone stream without sampleRate constraints
      // (iOS Safari / WebKit rejects sampleRate in getUserMedia with OverconstrainedError)
      try {
        micStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } catch (constraintErr) {
        console.warn('Advanced audio constraints rejected, falling back to basic audio:', constraintErr);
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }

      const source = audioCtx.createMediaStreamSource(micStream);
      scriptProcessor = audioCtx.createScriptProcessor(2048, 1, 1);

      // Connect microphone source to real-time audio analyser for frequency graph & VU meter
      const analyser = getAnalyser();
      if (analyser) {
        source.connect(analyser);
      }
      currentSourceType = 'mic';

      scriptProcessor.onaudioprocess = (e) => {
        if (!isRecording) return;
        const inputData = e.inputBuffer.getChannelData(0);

        // Dynamically resample device sample rate (e.g. 44.1kHz or 48kHz on Mac/iPad) down to 16kHz Int16 PCM
        const int16 = resampleAudioTo16k(inputData, audioCtx.sampleRate);

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

      // Route through a muted GainNode to prevent microphone audio from feeding into Mac speakers,
      // avoiding feedback howl and macOS CoreAudio feedback suppression/ducking.
      const muteNode = audioCtx.createGain();
      muteNode.gain.value = 0;
      source.connect(scriptProcessor);
      scriptProcessor.connect(muteNode);
      muteNode.connect(audioCtx.destination);

      isRecording = true;
      micBtn.classList.add('active');
      visualizer.classList.add('active');
      voiceHeading.textContent = isSimulated ? 'Listening to you...' : 'Listening to you (Gemini Live)...';
      voiceSubheading.textContent = 'Speak naturally, e.g. "Search travel headphones under ₹3,000"';
      logTelemetry('user', `Microphone active (${audioCtx.sampleRate}Hz -> 16kHz PCM). Ready for voice input.`);
    } catch (err) {
      console.error('Microphone access failed:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        showMicHelpModal(
          'Microphone Permission Required',
          `<p>The browser blocked microphone access on <strong>localhost:3000</strong>.</p>
           <p style="margin-top:8px"><strong>How to enable on your Mac / Mobile:</strong></p>
           <ul style="margin:8px 0 8px 20px;line-height:1.6">
             <li>In <strong>Chrome</strong>: Click the site settings icon (left of the address bar) &rarr; set <strong>Microphone</strong> to <strong>Allow</strong> &rarr; refresh.</li>
             <li>In <strong>Safari</strong>: Menu <em>Safari</em> &rarr; <em>Settings for this Website</em> &rarr; Microphone &rarr; <strong>Allow</strong>.</li>
             <li>In <strong>macOS System Settings</strong>: <em>Privacy &amp; Security &rarr; Microphone</em> &rarr; ensure your browser is enabled.</li>
             <li>On <strong>iPad / Mobile</strong>: Ensure connection is over <strong>HTTPS</strong> (use <code>npm run tunnel</code>).</li>
           </ul>`
        );
      } else if (err.name === 'SecurityError' || !window.isSecureContext) {
        showInsecureHelp();
      } else {
        showMicHelpModal('Microphone Error', `<p>${err.message || 'Could not access audio recording hardware.'}</p>`);
      }
    }
  }

  function stopRecording() {
    isRecording = false;
    currentSourceType = 'idle';
    micBtn.classList.remove('active');
    visualizer.classList.remove('active');
    voiceHeading.textContent = 'Tap Mic to Start Talking';
    voiceSubheading.textContent = 'Or type in the box below / use the 1-click Demo Triggers';

    if (speechRecognizer) {
      try {
        speechRecognizer.stop();
      } catch (e) {}
      speechRecognizer = null;
    }
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
      utterance.onstart = () => {
        currentSourceType = 'ai_synthetic';
      };
      utterance.onend = () => {
        if (!isRecording) currentSourceType = 'idle';
      };
      utterance.onerror = () => {
        if (!isRecording) currentSourceType = 'idle';
      };
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

  if (closeMicModalBtn) {
    closeMicModalBtn.addEventListener('click', () => {
      micHelpModal.classList.remove('open');
    });
  }

  if (bannerHelpBtn) {
    bannerHelpBtn.addEventListener('click', () => {
      showInsecureHelp();
    });
  }

  // Text Query Form Submission
  if (textQueryForm && textQueryInput) {
    textQueryForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const query = textQueryInput.value.trim();
      if (!query) return;

      logTelemetry('user', `Typed query: "${query}"`);
      voiceHeading.textContent = `"${query}"`;

      if (ws && ws.readyState === WebSocket.OPEN) {
        if (isSimulated) {
          ws.send(JSON.stringify({ type: 'simulate_query', text: query }));
        } else {
          ws.send(JSON.stringify({ type: 'text_query', text: query }));
        }
      }
      textQueryInput.value = '';
    });
  }

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

  // Load Initial Product Catalog & Cart on Page Load
  async function loadInitialCatalog() {
    try {
      const res = await fetch('/api/products');
      if (res.ok) {
        const data = await res.json();
        if (data.products && data.products.length > 0) {
          renderProducts(data.products);
          logTelemetry('system', `Initial catalogue loaded (${data.products.length} products).`);
        }
      }
      const cartRes = await fetch('/api/cart');
      if (cartRes.ok) {
        const cartData = await cartRes.json();
        renderCart(cartData);
      }
    } catch (err) {
      console.warn('Could not load initial catalog:', err);
    }
  }

  // Initial Boot
  connectWebSocket();
  checkInsecureContext();
  loadInitialCatalog();
  requestAnimationFrame(renderAudioHud);
})();
