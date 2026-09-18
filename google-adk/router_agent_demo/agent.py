"""Demo #3: the Router / Coordinator pattern.

One root agent, three specialists. The root has NO tools of its own - it
just reads the incoming message and decides WHICH specialist should answer,
via ADK's automatic LLM-driven delegation (a `transfer_to_agent` call the
framework wires up for you the moment an Agent has `sub_agents`).

Run `adk web`, pick router_agent_demo, and try:
    "I was charged twice for my subscription"      -> billing_agent
    "My app crashes with a NullPointerException"    -> tech_support_agent
    "What's the weather like today?"                -> general_agent
Watch the trace panel: the root agent's first move is a transfer, not an
answer of its own.
"""
from google.adk.agents import Agent

MODEL = "gemini-3.5-flash"

billing_agent = Agent(
    name="billing_agent",
    model=MODEL,
    description="Handles billing, payments, refunds, and subscription questions.",
    instruction=(
        "You are a billing support specialist. Help the user with charges, "
        "refunds, invoices, and subscription plans. Be empathetic and concise. "
        "If the question isn't about billing, say so plainly."
    ),
)

tech_support_agent = Agent(
    name="tech_support_agent",
    model=MODEL,
    description="Handles bugs, errors, crashes, and how-it-works technical questions.",
    instruction=(
        "You are a technical support specialist. Help the user debug errors, "
        "crashes, and 'how do I' technical questions. Ask a clarifying question "
        "if the report is too vague to act on."
    ),
)

general_agent = Agent(
    name="general_agent",
    model=MODEL,
    description="Handles greetings, small talk, and anything that isn't billing or tech support.",
    instruction=(
        "You are a friendly general assistant. Handle greetings and anything "
        "that doesn't clearly belong to billing or tech support."
    ),
)

# The root agent never answers directly - its only job is to pick a
# specialist. Having sub_agents is what makes ADK auto-wire the
# transfer_to_agent delegation tool.
root_agent = Agent(
    name="support_router",
    model=MODEL,
    description="Routes a user's message to the right support specialist.",
    instruction=(
        "You are a routing coordinator for a support desk. Read the user's "
        "message and immediately delegate to exactly one specialist:\n"
        "- billing_agent: charges, payments, refunds, invoices, subscriptions\n"
        "- tech_support_agent: bugs, errors, crashes, 'how do I' technical asks\n"
        "- general_agent: everything else (greetings, small talk, unclear asks)\n"
        "Do not attempt to answer the question yourself - always delegate."
    ),
    sub_agents=[billing_agent, tech_support_agent, general_agent],
)
