# Workshop 2: Multi-Agent Systems - Router, Sequential, Parallel & Loop

**Level:** Intermediate | **Duration:** ~90-120 min | **Env:** Google Cloud Shell

## What you'll build

Four small multi-agent apps, one per orchestration pattern, then deploy one
of them to Cloud Run:

| Pattern | Folder | What it teaches |
|---|---|---|
| Router / Coordinator | [`../router_agent_demo/`](../router_agent_demo/agent.py) | An LLM dynamically picks *which* sub-agent should answer |
| Sequential | [`../research_assistant/`](../research_assistant/agent.py) | A fixed pipeline: step 1 always runs before step 2 |
| Parallel | [`../parallel_agent_demo/`](../parallel_agent_demo/agent.py) | Independent sub-agents run concurrently, then get merged |
| Loop | [`../research_assistant/`](../research_assistant/agent.py) (the `refine_loop` part) | Repeat a critique/revise cycle until a condition is met |

## Prerequisites

Finish [Workshop 1](../workshop-1-agent-tools/README.md) first (or at least
the [one-time environment setup](../README.md#0-one-time-environment-setup-do-this-before-either-workshop)).
You should have `adk --version` working and your Gemini backend exported.

> If you're using the Gemini Developer API (`GOOGLE_API_KEY`), the built-in
> `google_search` tool used below works out of the box - no extra setup.
> If you're on Vertex AI, make sure `gcloud auth application-default login`
> has been run (Step 0.3 Option B in the main README).

---

## Concept overview (5 min, no coding)

ADK gives you a small set of **workflow agents** you compose like building
blocks. Each one just controls *how* its `sub_agents` run:

- **`SequentialAgent`** - runs sub-agents one after another, in order. Use when step B *needs* step A's output.
- **`ParallelAgent`** - runs sub-agents at the same time. Use when steps are independent and you want speed.
- **`LoopAgent`** - repeats its sub-agents until something calls `escalate` (or it hits `max_iterations`). Use for iterative refinement.
- **Router / Coordinator** - this isn't a special class, it's a plain `Agent` with `sub_agents=[...]` and no tools of its own. ADK auto-wires a `transfer_to_agent` tool, and the LLM decides at runtime which specialist gets the message. Use when the *right handler* depends on user intent.

All four can nest inside each other - a `SequentialAgent` step can itself be
a `ParallelAgent`, which is exactly what `parallel_agent_demo` does.

---

## Part A - Router / Coordinator pattern

Open [`../router_agent_demo/agent.py`](../router_agent_demo/agent.py). Three
specialists (`billing_agent`, `tech_support_agent`, `general_agent`), and a
root agent that has **no tools** - only `sub_agents` and an instruction
telling it to always delegate.

```python
root_agent = Agent(
    name="support_router",
    model=MODEL,
    description="Routes a user's message to the right support specialist.",
    instruction=(
        "You are a routing coordinator for a support desk. Read the user's "
        "message and immediately delegate to exactly one specialist:\n"
        "- billing_agent: charges, payments, refunds, invoices, subscriptions\n"
        "- tech_support_agent: bugs, errors, crashes, 'how do I' technical asks\n"
        "- general_agent: everything else\n"
        "Do not attempt to answer the question yourself - always delegate."
    ),
    sub_agents=[billing_agent, tech_support_agent, general_agent],
)
```

**Run it:**

```bash
adk web
```

Pick `router_agent_demo` and try, in order:
1. "I was charged twice for my subscription this month" → should transfer to `billing_agent`
2. "My app keeps crashing with a NullPointerException" → should transfer to `tech_support_agent`
3. "Hey, how's it going?" → should transfer to `general_agent`

Open the trace panel: the very first event from the root agent is a
`transfer_to_agent` function call - it never generates a text answer itself.

**Exercise:** each specialist's `description` field is what the router
reads to decide where to send things. Try weakening `tech_support_agent`'s
description to something vague and watch routing accuracy degrade - good
lesson that description quality *is* routing quality.

---

## Part B - Sequential pipeline pattern

Open [`../research_assistant/agent.py`](../research_assistant/agent.py) and
look at the bottom:

```python
root_agent = SequentialAgent(
    name="research_assistant",
    sub_agents=[researcher, writer, refine_loop],
)
```

`researcher` writes to `state["research"]`, `writer` reads `{research}` and
writes `state["draft"]`, and `refine_loop` (Part D, below) reads/rewrites
`{draft}`. Order is guaranteed - `writer` never runs before `researcher`
has finished.

**Run it:**

```bash
adk web
```

Pick `research_assistant` and ask: *"Summarize the latest on Google ADK"*.
Watch `researcher` → `writer` → the loop fire strictly in order in the
trace panel.

---

## Part C - Parallel fan-out/fan-in pattern

Open [`../parallel_agent_demo/agent.py`](../parallel_agent_demo/agent.py):

```python
gather = ParallelAgent(
    name="gather",
    sub_agents=[weather_agent, clock_agent, trivia_agent],
)

root_agent = SequentialAgent(
    name="city_briefing",
    sub_agents=[gather, synthesizer],
)
```

`weather_agent`, `clock_agent`, and `trivia_agent` don't depend on each
other, so they run **concurrently** inside `gather`, each writing to its own
`output_key`. Then `synthesizer` (a plain sequential step) reads all three
and merges them into one answer.

**Run it:**

```bash
adk web
```

Pick `parallel_agent_demo` and ask: *"Give me a briefing on Tokyo"*. In the
trace panel, compare the timestamps on `weather_agent`, `clock_agent`, and
`trivia_agent` - they overlap, unlike the strictly sequential steps in
Part B. That overlap *is* the performance win `ParallelAgent` buys you.

**Exercise:** add a fourth parallel branch (e.g. a `news_agent` using
`google_search`) and wire its `output_key` into the `synthesizer`
instruction template.

---

## Part D - Loop pattern (deep dive)

Back in `research_assistant/agent.py`, look at the `refine_loop`:

```python
def exit_loop(tool_context: ToolContext) -> dict:
    """Signal that the draft is approved and the refinement loop should stop."""
    tool_context.actions.escalate = True
    return {"status": "approved"}

critic = Agent(..., tools=[exit_loop], output_key="critique")
reviser = Agent(..., output_key="draft")

refine_loop = LoopAgent(
    name="refine_loop",
    max_iterations=3,
    sub_agents=[critic, reviser],
)
```

Every pass: `critic` reads `{draft}` and either calls `exit_loop` (draft is
good) or writes actionable feedback to `{critique}`; `reviser` applies that
feedback and overwrites `{draft}`. The loop keeps going until `exit_loop`
fires **or** `max_iterations` is hit - that cap is your safety net against
an agent that never agrees its own work is good enough.

**Run it:** same `research_assistant` session from Part B - watch the trace
panel count `critic` → `reviser` passes and stop the moment `exit_loop` is
called (often before hitting the 3-pass cap).

---

## Stretch goal (optional, ~15 min)

Combine two patterns: make `router_agent_demo`'s `tech_support_agent` a
`SequentialAgent` of its own (e.g. a "diagnose" step then a "suggest fix"
step), or give it its own small `LoopAgent` for iterative troubleshooting.
Nesting is the whole point - a workflow agent is just another `Agent` as
far as its parent is concerned.

---

## Deploy a multi-agent app to Cloud Run

We'll deploy `research_assistant` since it already ships with `.env`-style
docs. Same command shape as Workshop 1, just a different folder - use
whichever backend column matches your setup.

**Option A - Gemini Developer API:**
```bash
adk deploy cloud_run research_assistant -- \
  --region=us-central1 \
  --set-env-vars=GOOGLE_API_KEY=YOUR_GEMINI_API_KEY,GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

**Option B - Vertex AI:**
```bash
# One-time per project (skip if you already did this in Workshop 1):
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

adk deploy cloud_run research_assistant -- \
  --region=us-central1 \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

> Same deal for `router_agent_demo` and `parallel_agent_demo` if you want to
> deploy one of those instead - just swap the folder name, the flags don't change.

Note the service URL, then create a session and invoke it exactly like
Workshop 1:

```bash
export SERVICE_URL="https://adk-default-service-name-XXXXXXXXXX.us-central1.run.app"

curl -X POST "$SERVICE_URL/apps/research_assistant/users/u_123/sessions/s_1" \
  -H "Content-Type: application/json" -d '{}'

curl -X POST "$SERVICE_URL/run" \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "research_assistant",
    "userId": "u_123",
    "sessionId": "s_1",
    "newMessage": {
      "role": "user",
      "parts": [{"text": "Help me research Google ADK."}]
    }
  }'
```

The response event stream will show the full pipeline: `researcher` →
`writer` → `critic`/`reviser` loop passes → final draft. Full details on
the deploy/session/run flow are also in
[`../research_assistant/README.md`](../research_assistant/README.md).

### Clean up

```bash
gcloud run services delete adk-default-service-name --region=us-central1
```

---

## Recap

- **Router**: `Agent` + `sub_agents`, no tools of its own → LLM picks the specialist at runtime.
- **Sequential**: `SequentialAgent` → guaranteed order, data flows via `state`/`output_key`.
- **Parallel**: `ParallelAgent` → concurrent independent work, fanned back in by a following step.
- **Loop**: `LoopAgent` + an `exit_loop` tool that sets `tool_context.actions.escalate = True`, capped by `max_iterations`.
- All four nest inside each other - mix and match to fit the shape of the real problem.
- Deployment story is identical across all patterns: `adk deploy cloud_run <folder>`.

**Resources:** [Google ADK docs](https://google.github.io/adk-docs/) · [`google.adk.agents` API reference](https://google.github.io/adk-docs/agents/)
