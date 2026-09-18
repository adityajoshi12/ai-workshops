# Workshop 1: Your First ADK Agent + Custom Tools

**Level:** Beginner | **Duration:** ~60-90 min | **Env:** Google Cloud Shell

## What you'll build

A single conversational agent that answers weather and time questions using
two **custom tools** you write yourself — then you'll deploy it to
**Cloud Run** and call it over HTTP like a real service.

## Learning objectives

By the end you'll be able to:
- Explain what an ADK `Agent` is (model + instruction + tools)
- Explain what a "tool" is and how the LLM decides when to call one
- Scaffold, run, and test an agent locally with the `adk` CLI
- Deploy an agent to Cloud Run and talk to it via REST

> Solution code for this whole workshop already lives in [`../my_agent/`](../my_agent/agent.py)
> — try building it yourself first, peek only if stuck.

---

## Step 0 — Environment check

Make sure you completed the [one-time setup](../README.md#0-one-time-environment-setup-do-this-before-either-workshop)
(APIs enabled, `GOOGLE_API_KEY` or Vertex vars exported, venv active,
`adk --version` works). Do this in Cloud Shell, in the `google-adk/` folder.

---

## Step 1 — Scaffold a new agent

```bash
adk create my_agent
```

This generates:

```text
my_agent/
  __init__.py     # from . import agent
  agent.py        # your root_agent lives here
  .env            # env vars auto-loaded by ADK (API key / Vertex config)
```

Open it in the **Cloud Shell Editor** (pencil icon, top-right) — it's just
VS Code in your browser.

Drop your backend choice from Step 0 into `my_agent/.env`, e.g.:

```dotenv
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

---

## Step 2 — Anatomy of an `Agent`

Open the generated `agent.py`. Every ADK agent boils down to four things:

```python
from google.adk.agents import Agent

root_agent = Agent(
    model="gemini-2.5-flash",       # which LLM powers it
    name="root_agent",              # unique id
    description="...",              # used by OTHER agents to decide to route to this one
    instruction="...",              # the system prompt - the agent's "job description"
    tools=[],                       # python functions the model can call
)
```

The **instruction** is doing the heavy lifting: it tells the model what
it's allowed to do, and — crucially — when to reach for a tool instead of
guessing an answer.

---

## Step 3 — Write your first tool: `get_weather`

A "tool" in ADK is just a plain Python function with a docstring. The
docstring **is** the tool's API contract — the model reads it to decide
whether and how to call it. Add this to `agent.py`:

```python
import requests

def get_weather(city: str) -> dict:
    """Return the current weather for a given city.

    Args:
        city: Name of the city, e.g. "Bengaluru". Case-insensitive.

    Returns:
        On success: {"status": "ok", "city": "<City>", "weather": "<summary>"}
        On failure: {"status": "error", "error_message": "<details>"}
    """
    try:
        response = requests.get(f"https://wttr.in/{city}?format=3", timeout=10)
        response.raise_for_status()
        return {"status": "ok", "city": city.title(), "weather": response.text.strip()}
    except requests.RequestException as e:
        return {"status": "error", "error_message": f"Failed to fetch weather: {e}"}
```

Two rules that matter a lot more than they look like they should:
1. **Type hints are required** — ADK uses them to build the function schema the model sees.
2. **Always return a dict with a `status` key** — it gives the model (and the instruction) a clean way to branch on success/failure instead of guessing from free text.

---

## Step 4 — Write a second tool: `get_current_time`

```python
from datetime import datetime
from zoneinfo import ZoneInfo

_CITY_TZ = {
    "bengaluru": "Asia/Kolkata",
    "london": "Europe/London",
    "new york": "America/New_York",
    "tokyo": "Asia/Tokyo",
}

def get_current_time(city: str) -> dict:
    """Return the current local time for a given city.

    Args:
        city: Name of the city, e.g. "Tokyo". Case-insensitive.

    Returns:
        On success: {"status": "ok", "city", "current_time"}.
        On failure: {"status": "error", "error_message"} if unsupported.
    """
    tz_name = _CITY_TZ.get(city.strip().lower())
    if tz_name is None:
        return {
            "status": "error",
            "error_message": f"No timezone for '{city}'. Supported: {', '.join(sorted(_CITY_TZ))}.",
        }
    now = datetime.now(ZoneInfo(tz_name))
    return {"status": "ok", "city": city.title(), "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z")}
```

---

## Step 5 — Wire the tools into the agent

```python
root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="A helpful assistant that answers weather and time questions.",
    instruction=(
        "You are a friendly assistant. "
        "Use the get_weather tool for weather questions and the "
        "get_current_time tool for time questions. "
        "If a tool returns status 'error', apologize and pass along the "
        "error_message so the user knows which cities are supported. "
        "Never invent weather or time data - always call a tool."
    ),
    tools=[get_weather, get_current_time],
)
```

That last instruction line ("never invent... always call a tool") matters —
without it, small models will happily hallucinate a plausible-looking
forecast instead of calling your tool.

---

## Step 6 — Run it locally

**Option A — Web UI (recommended for the trace panel):**

```bash
adk web
```

Cloud Shell will offer a **Web Preview** on port 8000 — click it, pick
`my_agent` from the dropdown, and chat. Open the trace/events panel and
watch the model **decide** to call `get_weather` — that decision is the
whole point of the demo.

**Option B — Terminal chat:**

```bash
adk run my_agent
```

Try:
- "What's the weather in Tokyo?"
- "What time is it in London?"
- "What's the weather on Mars?" → watch it surface your `error_message` instead of making something up.

---

## Step 7 — Exercise (do this yourselves, ~10 min)

Add a **third tool** of your own choosing. Ideas:
- `convert_currency(amount, from_currency, to_currency)` (hit a free FX API)
- `get_joke()` (hit `https://official-joke-api.appspot.com/random_joke`)
- `roll_dice(sides)` (pure Python, no API needed — good if you're offline)

Requirements: type hints, a docstring, and a `status` key in the return
dict. Add it to `tools=[...]` and update the instruction to mention it.

---

## Step 8 — Deploy to Cloud Run

```bash
adk deploy cloud_run my_agent -- \
  --region=us-central1 \
  --set-env-vars=GOOGLE_API_KEY=YOUR_GEMINI_API_KEY,GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

(If you went the Vertex route in Step 0, swap the env vars for
`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=TRUE`
instead.)

This builds a container (via Cloud Build), pushes it to Artifact Registry,
and deploys it to Cloud Run. Note the printed service URL, e.g.:

```text
https://adk-default-service-name-XXXXXXXXXX.us-central1.run.app
```

---

## Step 9 — Talk to your deployed agent over HTTP

**Create a session:**

```bash
export SERVICE_URL="https://adk-default-service-name-XXXXXXXXXX.us-central1.run.app"

curl -X POST "$SERVICE_URL/apps/my_agent/users/u_123/sessions/s_1" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Send a message:**

```bash
curl -X POST "$SERVICE_URL/run" \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "my_agent",
    "userId": "u_123",
    "sessionId": "s_1",
    "newMessage": {
      "role": "user",
      "parts": [{"text": "What is the weather in London?"}]
    }
  }'
```

You should get back the full event stream, including the tool call and its
result — same thing you saw in the local trace panel, just over the wire.

---

## Step 10 — Clean up (optional, avoids ongoing cost)

```bash
gcloud run services delete adk-default-service-name --region=us-central1
```

---

## Recap

- An **Agent** = model + instruction + tools.
- A **tool** = a typed, documented Python function; the docstring is the contract the LLM reads.
- Always return structured `status`/`error_message` dicts from tools so the model — and your instruction — can react cleanly to failure.
- `adk web` / `adk run` for local iteration, `adk deploy cloud_run` to ship it.

**Next up:** [Workshop 2 — Multi-Agent Systems](../workshop-2-multi-agent/README.md), where one agent becomes a team.
