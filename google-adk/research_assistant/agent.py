"""Demo #2: a multi-agent research assistant.

The autonomy story from the deck, made real:

    research_pipeline (SequentialAgent)
      1. researcher  - uses google_search to gather current facts   -> state["research"]
      2. writer      - drafts a crisp summary from the research      -> state["draft"]
      3. refine_loop (LoopAgent, up to N passes)
           a. critic  - fact-checks + tightens; calls exit_loop when good
           b. reviser - rewrites the draft using the critic's notes  -> state["draft"]

Run `adk web`, pick research_assistant, and ask:
    "Summarize the latest on Google ADK"
Then watch each sub-agent fire in the trace panel, and watch the loop stop
itself the moment the critic is satisfied.
"""
from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools import google_search
from google.adk.tools.tool_context import ToolContext

MODEL = "gemini-3.5-flash"
MAX_REFINEMENT_PASSES = 3

# Sentinel the critic emits when the draft is good enough to ship.
APPROVED = "APPROVED"


def exit_loop(tool_context: ToolContext) -> dict:
    """Signal that the draft is approved and the refinement loop should stop.

    Call this ONLY when the current draft needs no further changes.
    """
    tool_context.actions.escalate = True  # breaks out of the enclosing LoopAgent
    return {"status": "approved"}


# 1. RESEARCH - the only agent with a tool; gathers current facts.
researcher = Agent(
    name="researcher",
    model=MODEL,
    description="Gathers current facts on a topic using Google Search.",
    instruction=(
        "You are a researcher. Use the google_search tool to gather current, "
        "accurate facts about the user's topic. Return a concise, bulleted list "
        "of the key findings with any relevant numbers, dates, and names. "
        "Do not write prose - just the facts."
    ),
    tools=[google_search],
    output_key="research",
)

# 2. WRITE - turns raw research into a first-draft summary.
writer = Agent(
    name="writer",
    model=MODEL,
    description="Drafts a crisp summary from the research findings.",
    instruction=(
        "You are a technical writer. Using ONLY the research below, write a "
        "clear, well-structured summary of about 150 words for a smart but "
        "non-expert reader. Do not invent facts beyond the research.\n\n"
        "Research:\n{research}"
    ),
    output_key="draft",
)

# 3a. CRITIQUE - reviews the draft; approves or returns specific fixes.
critic = Agent(
    name="critic",
    model=MODEL,
    description="Fact-checks and critiques the current draft.",
    instruction=(
        "You are a sharp editor. Review the draft below against the research.\n\n"
        "Research:\n{research}\n\n"
        "Current draft:\n{draft}\n\n"
        f"If the draft is accurate, clear, and well-structured, call the "
        f"exit_loop tool and reply exactly '{APPROVED}'. "
        "Otherwise, do NOT call the tool - instead list 2-4 specific, "
        "actionable fixes (accuracy, clarity, or structure). Be concise."
    ),
    tools=[exit_loop],
    output_key="critique",
)

# 3b. REVISE - applies the critic's notes to produce a better draft.
reviser = Agent(
    name="reviser",
    model=MODEL,
    description="Rewrites the draft using the critic's feedback.",
    instruction=(
        "You are a writer revising your work. Apply the editor's feedback to "
        "improve the draft. Output ONLY the revised summary - no preamble.\n\n"
        "Research:\n{research}\n\n"
        "Previous draft:\n{draft}\n\n"
        "Editor feedback:\n{critique}"
    ),
    output_key="draft",
)

# The critique/revise cycle: loops until the critic escalates (or hits the cap).
refine_loop = LoopAgent(
    name="refine_loop",
    max_iterations=MAX_REFINEMENT_PASSES,
    sub_agents=[critic, reviser],
)

# The full deterministic pipeline: research -> write -> refine.
root_agent = SequentialAgent(
    name="research_assistant",
    description="Researches a topic, writes a summary, and self-edits it.",
    sub_agents=[researcher, writer, refine_loop],
)"""Demo #2: a multi-agent research assistant.

The autonomy story from the deck, made real:

    research_pipeline (SequentialAgent)
      1. researcher  - uses google_search to gather current facts   -> state["research"]
      2. writer      - drafts a crisp summary from the research      -> state["draft"]
      3. refine_loop (LoopAgent, up to N passes)
           a. critic  - fact-checks + tightens; calls exit_loop when good
           b. reviser - rewrites the draft using the critic's notes  -> state["draft"]

Run `adk web`, pick research_assistant, and ask:
    "Summarize the latest on Google ADK"
Then watch each sub-agent fire in the trace panel, and watch the loop stop
itself the moment the critic is satisfied.
"""
from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools import google_search
from google.adk.tools.tool_context import ToolContext

MODEL = "gemini-3.5-flash"
MAX_REFINEMENT_PASSES = 3

# Sentinel the critic emits when the draft is good enough to ship.
APPROVED = "APPROVED"


def exit_loop(tool_context: ToolContext) -> dict:
    """Signal that the draft is approved and the refinement loop should stop.

    Call this ONLY when the current draft needs no further changes.
    """
    tool_context.actions.escalate = True  # breaks out of the enclosing LoopAgent
    return {"status": "approved"}


# 1. RESEARCH - the only agent with a tool; gathers current facts.
researcher = Agent(
    name="researcher",
    model=MODEL,
    description="Gathers current facts on a topic using Google Search.",
    instruction=(
        "You are a researcher. Use the google_search tool to gather current, "
        "accurate facts about the user's topic. Return a concise, bulleted list "
        "of the key findings with any relevant numbers, dates, and names. "
        "Do not write prose - just the facts."
    ),
    tools=[google_search],
    output_key="research",
)

# 2. WRITE - turns raw research into a first-draft summary.
writer = Agent(
    name="writer",
    model=MODEL,
    description="Drafts a crisp summary from the research findings.",
    instruction=(
        "You are a technical writer. Using ONLY the research below, write a "
        "clear, well-structured summary of about 150 words for a smart but "
        "non-expert reader. Do not invent facts beyond the research.\n\n"
        "Research:\n{research}"
    ),
    output_key="draft",
)

# 3a. CRITIQUE - reviews the draft; approves or returns specific fixes.
critic = Agent(
    name="critic",
    model=MODEL,
    description="Fact-checks and critiques the current draft.",
    instruction=(
        "You are a sharp editor. Review the draft below against the research.\n\n"
        "Research:\n{research}\n\n"
        "Current draft:\n{draft}\n\n"
        f"If the draft is accurate, clear, and well-structured, call the "
        f"exit_loop tool and reply exactly '{APPROVED}'. "
        "Otherwise, do NOT call the tool - instead list 2-4 specific, "
        "actionable fixes (accuracy, clarity, or structure). Be concise."
    ),
    tools=[exit_loop],
    output_key="critique",
)

# 3b. REVISE - applies the critic's notes to produce a better draft.
reviser = Agent(
    name="reviser",
    model=MODEL,
    description="Rewrites the draft using the critic's feedback.",
    instruction=(
        "You are a writer revising your work. Apply the editor's feedback to "
        "improve the draft. Output ONLY the revised summary - no preamble.\n\n"
        "Research:\n{research}\n\n"
        "Previous draft:\n{draft}\n\n"
        "Editor feedback:\n{critique}"
    ),
    output_key="draft",
)

# The critique/revise cycle: loops until the critic escalates (or hits the cap).
refine_loop = LoopAgent(
    name="refine_loop",
    max_iterations=MAX_REFINEMENT_PASSES,
    sub_agents=[critic, reviser],
)

# The full deterministic pipeline: research -> write -> refine.
root_agent = SequentialAgent(
    name="research_assistant",
    description="Researches a topic, writes a summary, and self-edits it.",
    sub_agents=[researcher, writer, refine_loop],
)

