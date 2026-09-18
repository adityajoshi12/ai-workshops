# Google ADK Hands-On Workshops

Two back-to-back, hands-on labs for learning the **Google Agent Development
Kit (ADK)** — from a single tool-calling agent to full multi-agent systems,
deployed to Cloud Run. Built for **beginner-to-intermediate** developers who
know basic Python but have never touched an agent framework.

Everything runs in **Google Cloud Shell** (browser terminal + Cloud Shell
Editor) — no local install required.

| Workshop | Topic | Duration | Folder |
|---|---|---|---|
| 1 | Single agent + custom tools (weather/time bot) | ~60-90 min | [`workshop-1-agent-tools/`](./workshop-1-agent-tools/README.md) |
| 2 | Multi-agent: Router, Sequential, Parallel, Loop | ~90-120 min | [`workshop-2-multi-agent/`](./workshop-2-multi-agent/README.md) |

Both workshops end the same way: `adk deploy cloud_run`, then poke the live
agent with `curl`.

## Repo map

```text
google-adk/
  my_agent/              # Workshop 1 solution - single agent, 2 custom tools
  router_agent_demo/     # Workshop 2 - Router / Coordinator pattern
  research_assistant/    # Workshop 2 - Sequential + Loop pattern
  parallel_agent_demo/   # Workshop 2 - Parallel fan-out/fan-in pattern
  workshop-1-agent-tools/README.md
  workshop-2-multi-agent/README.md
```

Every agent folder is a **standalone, independently runnable ADK app**
(`adk run <folder>` / `adk web`) — that's an ADK convention, not a
duplication accident. Small bits of tool code (like the weather lookup) are
intentionally re-declared in a couple of folders so each lab stands on its
own and attendees don't have to jump between directories mid-exercise.

---

## 0. One-time environment setup (do this before either workshop)

Do this once, in **Cloud Shell** (top-right `>_` icon in the Cloud Console,
or open the **Cloud Shell Editor** for a VS Code-like experience with an
integrated terminal at the bottom).

### 0.1 Pick / confirm your project

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud config get-value project
```

### 0.2 Enable the required APIs

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  generativelanguage.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com
```

What each one is for:

| API | Why you need it |
|---|---|
| `aiplatform.googleapis.com` | Vertex AI backend for Gemini (if you go the Vertex route) |
| `generativelanguage.googleapis.com` | Gemini Developer API backend (if you go the API-key route) |
| `run.googleapis.com` | Cloud Run — where the agent gets deployed |
| `cloudbuild.googleapis.com` | `adk deploy cloud_run` builds a container behind the scenes |
| `artifactregistry.googleapis.com` | Stores the built container image |
| `iam.googleapis.com` | Service account permissions for the above |

### 0.3 Choose a Gemini backend — pick ONE

**Option A — Gemini Developer API (simplest, good for workshops):**

1. Grab a free key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Export it in Cloud Shell:
   ```bash
   export GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
   export GOOGLE_GENAI_USE_VERTEXAI=FALSE
   ```

**Option B — Vertex AI (uses your GCP project's quota/billing, no separate key):**

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

> Whichever option you pick, you'll drop the *same* variables into a
> `.env` file inside each agent folder later — ADK auto-loads it.

### 0.4 Python environment + install the ADK

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install google-adk requests
```

Check it installed:

```bash
adk --version
```

You're set. Head to **[Workshop 1](./workshop-1-agent-tools/README.md)**.
