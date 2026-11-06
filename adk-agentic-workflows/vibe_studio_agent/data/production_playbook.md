# VibeStudio 24-Second Production Playbook (DOC-PLAYBOOK-02)

## 1. The 3-Scene Temporal Architecture (3 x 8s = 24s)
Google Veo generates optimal temporal coherence in 8-second clips. Every VibeStudio storyboard **must** be structured into exactly **3 scenes**:

1. **Scene 1 — The Visual Hook (0s–8s):**
   - **Goal:** Stop the scroll within the first 2 seconds using kinetic motion or a striking visual contrast.
   - **Camera:** Dynamic opening movement (`dolly-in`, `crane reveal`, or `macro push-in`).
   - **Voiceover:** 15–20 words posing a compelling question or surprising fact.

2. **Scene 2 — The Core Mechanism / Turn (8s–16s):**
   - **Goal:** Demonstrate the core concept, transformation, or architectural insight visually.
   - **Camera:** Steady tracking shot or split-depth perspective (`35mm lens, shallow depth of field`).
   - **Voiceover:** 18–22 words explaining *how* or *why* it works.

3. **Scene 3 — The Payoff & Call-to-Curiosity (16s–24s):**
   - **Goal:** Deliver a memorable visual resolution and loop smoothly back to Scene 1.
   - **Camera:** Wide pull-back or slow hero orbit (`golden hour rim lighting`).
   - **Voiceover:** 12–18 words with a crisp takeaway.

## 2. Asset Pipeline Order of Operations
1. **Parallel Research & Knowledge Ingestion:** Gather topical trends + retrieve brand & playbook rules concurrently.
2. **Storyboard Drafting & Self-Critique Loop:** Validate 3-scene structure, 24s duration, lighting/camera specs, and zero banned tropes.
3. **Human-in-the-Loop (HITL) Sign-Off:** Pause execution (`request_creator_signoff`) so the creator approves the storyboard before spending GPU compute.
4. **Reference Keyframe Generation (Imagen 3):** Render 16:9 or 9:16 anchor frames (`generate_scene_frames`) for each approved scene.
5. **Asynchronous Video Rendering (Google Veo):** Trigger `start_veo_video_render` via `LongRunningFunctionTool` and poll/resume via operation ID.
