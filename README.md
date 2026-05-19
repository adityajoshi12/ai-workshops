# AI Agent Workshops

Hands-on workshops for building AI agents with Google Gemini.

---

## Workshops

| Workshop | Stack | What you build |
|---|---|---|
| [`ai-agent-langchain/`](./ai-agent-langchain/) | TypeScript · LangChain · LangGraph | ReAct agent with tools and conversation memory |
| [`smart-email-agent/`](./smart-email-agent/) | Go · Google ADK · MCP | Gmail-backed inbox agent with sub-agent delegation |

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

## Author

**Aditya Joshi** — [YouTube](https://www.youtube.com/@adityajoshi12) · [LinkedIn](https://www.linkedin.com/in/adityajoshi12) · [connect@adityajoshi.online](mailto:connect@adityajoshi.online)

---

## Prerequisites

- **ai-agent-langchain**: Node.js 18+, a Gemini API key
- **smart-email-agent**: Go, Node.js (for the Gmail MCP server), a Gemini API key + Gmail account
