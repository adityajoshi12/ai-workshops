# AI Agent Workshops

Hands-on workshops for building AI agents with Google Gemini.

---

## Workshops

| Workshop | Stack | What you build |
|---|---|---|
| [`ai-agent-langchain/`](./ai-agent-langchain/) | TypeScript · LangChain · LangGraph | ReAct agent with tools and conversation memory |
| [`smart-email-agent/`](./smart-email-agent/) | Go · Google ADK · MCP | Gmail-backed inbox agent with sub-agent delegation |
| [`agent-sandbox-gke/`](./agent-sandbox-gke/) | Python · Google ADK · GKE Agent Sandbox | Autonomous coding agent running inside gVisor-isolated Kubernetes sandboxes |
| [`talk-to-shop-gemini-live/`](./talk-to-shop-gemini-live/) | TypeScript · Fastify · Gemini Live API · Web Audio | Voice-first e-commerce shopping agent with Dual Delivery UI and authoritative backend |
| [`mem0-gemini-memory/`](./mem0-gemini-memory/) | Python · mem0 · Gemini | Chatbot with long-term memory that remembers you across runs |

---

## ai-agent-langchain

Build a tool-calling agent using LangChain and Google Gemini. Covers tool definition, ReAct reasoning loops, and multi-turn memory via LangGraph checkpoints.

- [Part 1 — Tools & ReAct agents](./ai-agent-langchain/WORKSHOP_PART1.md)
- [Part 2 — Memory & persistence](./ai-agent-langchain/WORKSHOP_PART2.md)

```bash
cd ai-agent-langchain
npm install
npm start
```

---

## smart-email-agent

Build a Gmail agent using Google ADK. Classifies emails, drafts replies, and delegates to sub-agents. Runs as a console app or web UI, and deploys to Cloud Run.

- [Setup & walkthrough](./smart-email-agent/README.md)

```bash
cd smart-email-agent
go run . console
```

---

## talk-to-shop-gemini-live

Build a real-time, bidirectional voice e-commerce shopping agent powered by Google Gemini Live API (`gemini-2.5-flash-native-audio-preview-12-2025`). Implements Dual Delivery architecture (voice audio + synchronized visual product cards), function calling with 9 commerce tools, client-side Web Audio (16kHz PCM capture, 24kHz PCM playback), and instant barge-in interruption.

- [Setup & walkthrough](./talk-to-shop-gemini-live/README.md)

```bash
cd talk-to-shop-gemini-live
npm install
cp .env.example .env  # Add your GEMINI_API_KEY
npm run dev
```

---

---

## mem0-gemini-memory

A short demo of long-term memory: mem0 stores facts from each chat, and Gemini answers using them. Quit, restart, and the bot still remembers you.

- [Setup & walkthrough](./mem0-gemini-memory/README.md)

```bash
cd mem0-gemini-memory
pip install -r requirements.txt
python demo.py
```

---

## Author

**Aditya Joshi** — [YouTube](https://www.youtube.com/@adityajoshi12) · [LinkedIn](https://www.linkedin.com/in/adityajoshi12) · [connect@adityajoshi.online](mailto:connect@adityajoshi.online)

---

## Prerequisites

- **ai-agent-langchain**: Node.js 18+, a Gemini API key
- **smart-email-agent**: Go, Node.js (for the Gmail MCP server), a Gemini API key + Gmail account
- **agent-sandbox-gke**: Python 3.11+, GKE cluster with gVisor sandbox enabled, Gemini API key
- **talk-to-shop-gemini-live**: Node.js 18+, a Gemini API key (supports Gemini 2.5 Flash Native Audio preview)
- **mem0-gemini-memory**: Python 3.10+, a Gemini API key
