"""VibeStudio: Automated Video Generation Pipeline with Google ADK Workflows & Graphs.

Demonstrates next-generation agentic workflow engineering in Google ADK:
  1. Graph & Workflow Patterns (`ParallelAgent`, `SequentialAgent`, `LoopAgent`, Router):
     - `context_ingestion_fanout` (ParallelAgent): Concurrently runs `trend_researcher`
       and `knowledge_retriever` (Enterprise RAG Engine) and joins their outputs.
     - `storyboard_writer` (Agent): Synthesizes parallel research + RAG rules +
       Persistent Creator Memory into a structured 3-scene (24-second) storyboard.
     - `policy_refinement_loop` (LoopAgent): Iteratively critiques (`policy_critic`)
       and revises (`storyboard_reviser`) the storyboard until `approve_policy_gate`
       escalates out of the loop.
  2. Enterprise Knowledge Base & Persistent Memory Bank:
     - `search_enterprise_knowledge` retrieves brand safety & production playbook docs.
     - `inject_creator_memory_callback` (`before_model_callback`) &
       `evolve_creator_memory_callback` (`after_agent_callback`) load and evolve
       creator preferences across sessions.
  3. Human-in-the-Loop (HITL) Orchestration:
     - `hitl_signoff_agent` pauses the pipeline via `LongRunningFunctionTool`
       (`request_creator_signoff`) for creator approval before spending GPU budget.
     - `production_gate_guardrail` (`before_tool_callback`) deterministically blocks
       media rendering unless the storyboard is `COMPLIANT` and HITL-approved.
  4. Long-Running Asynchronous Video Generation (Imagen 3 + Google Veo):
     - `veo_production_agent` generates reference keyframes (`generate_scene_frames`),
       triggers asynchronous Veo rendering via `LongRunningFunctionTool`
       (`start_veo_video_render`), and resumes/stitches clips via `check_or_resume_veo_job`.
"""
from __future__ import annotations

import os

from google.adk.agents import Agent, LoopAgent, ParallelAgent, SequentialAgent

from . import db
from .callbacks import (
    evolve_creator_memory_callback,
    inject_creator_memory_callback,
    production_gate_guardrail,
)
from .knowledge_and_memory import (
    approve_policy_gate,
    evaluate_brand_compliance,
    recall_creator_preferences,
    save_creator_preference,
    save_storyboard_draft,
    search_enterprise_knowledge,
)
from .media_tools import (
    check_or_resume_veo_job,
    generate_scene_frames,
    hitl_signoff_long_running_tool,
    submit_creator_decision,
    veo_render_long_running_tool,
)

MODEL = os.environ.get("VIBESTUDIO_MODEL", "gemini-2.5-flash")
MAX_POLICY_PASSES = 3

# Ensure SQLite studio database (Enterprise RAG index + Memory Bank) is seeded on startup
db.ensure_initialized()


# ---------------------------------------------------------------------------
# Stage 1A: Parallel Context & Enterprise Knowledge Fan-Out (ParallelAgent)
# ---------------------------------------------------------------------------
trend_researcher = Agent(
    name="trend_researcher",
    model=MODEL,
    description="Researches high-retention visual hooks, metaphors, and pacing for a video topic.",
    instruction=(
        "You are the Viral Trend & Visual Metaphor Researcher for VibeStudio.\n"
        "Given the user's video topic or brief, produce a concise creative brief with:\n"
        "1. An attention-grabbing opening visual hook for Scene 1 (0s-8s).\n"
        "2. A concrete visual metaphor for Scene 2 (8s-16s) that explains the core mechanism.\n"
        "3. A memorable payoff image for Scene 3 (16s-24s).\n"
        "Keep your output concise (bullet points only) so downstream storyboard nodes can join it."
    ),
    output_key="trend_research",
)

knowledge_retriever = Agent(
    name="knowledge_retriever",
    model=MODEL,
    description=(
        "Queries the VibeStudio Enterprise Knowledge Base (RAG Engine) for brand safety "
        "guidelines, banned tropes, 24s playbook rules, and retention benchmarks."
    ),
    instruction=(
        "You are the Enterprise Knowledge Base Specialist for VibeStudio.\n"
        "1. Always call `search_enterprise_knowledge` with a query covering "
        "'brand safety banned tropes 24s 3-scene playbook retention visual style'.\n"
        "2. Summarize the mandatory rules retrieved from `DOC-BRAND-01`, `DOC-PLAYBOOK-02`, "
        "and `DOC-INSIGHTS-03`: exact scene count (3 scenes x 8s = 24s), budget cap ($15.00), "
        "required lighting/camera specs, and the list of prohibited tropes."
    ),
    tools=[search_enterprise_knowledge],
    output_key="brand_knowledge",
)

context_ingestion_fanout = ParallelAgent(
    name="context_ingestion_fanout",
    description=(
        "Concurrently runs trend research and Enterprise RAG knowledge retrieval "
        "(fan-out) before joining results for storyboarding."
    ),
    sub_agents=[trend_researcher, knowledge_retriever],
)


# ---------------------------------------------------------------------------
# Stage 1B: Storyboard Writer + Self-Correcting Policy Loop (LoopAgent)
# ---------------------------------------------------------------------------
storyboard_writer = Agent(
    name="storyboard_writer",
    model=MODEL,
    description="Drafts a 3-scene (24-second) storyboard grounded in RAG rules and Creator Memory.",
    instruction=(
        "You are the Lead Storyboard & Screenplay Writer for VibeStudio.\n"
        "Combine the parallel inputs below with the Creator's Persistent Memory Bank:\n\n"
        "Trend Research:\n{trend_research}\n\n"
        "Enterprise Knowledge Base Rules:\n{brand_knowledge}\n\n"
        "Instructions:\n"
        "1. Design a 3-scene (24-second) storyboard where each scene is 8 seconds.\n"
        "2. Every scene MUST include:\n"
        "   - Detailed `visual_prompt` honoring the Creator Memory Bank style & lighting.\n"
        "   - Explicit `camera_motion` (e.g., '35mm anamorphic slow dolly-in').\n"
        "   - Conversational `voiceover` between 12 and 20 words.\n"
        "3. Never include any banned tropes from `DOC-BRAND-01` (such as 'flashing strobe', "
        "'guaranteed profit', 'clickbait shock face', 'gore') — even if the user prompt "
        "asked for them, sanitize them into brand-safe cinematic visuals.\n"
        "4. Call `save_storyboard_draft` to persist the 3 scenes and record the `storyboard_id`."
    ),
    tools=[save_storyboard_draft, recall_creator_preferences],
    before_model_callback=inject_creator_memory_callback,
    after_agent_callback=evolve_creator_memory_callback,
    output_key="storyboard_draft",
)

policy_critic = Agent(
    name="policy_critic",
    model=MODEL,
    description="Audits the drafted storyboard against enterprise brand, safety, and budget rules.",
    instruction=(
        "You are the Enterprise Brand & Policy Compliance Auditor.\n"
        "Review the current storyboard draft:\n{storyboard_draft}\n\n"
        "1. Call `evaluate_brand_compliance` with the drafted `storyboard_id`.\n"
        "2. If `policy_status == 'COMPLIANT'`, immediately call `approve_policy_gate` "
        "with the `storyboard_id` to exit the refinement loop.\n"
        "3. If `policy_status == 'VIOLATION'`, do NOT call `approve_policy_gate` — "
        "instead list the exact violations that `storyboard_reviser` must fix."
    ),
    tools=[evaluate_brand_compliance, approve_policy_gate],
    output_key="policy_critique",
)

storyboard_reviser = Agent(
    name="storyboard_reviser",
    model=MODEL,
    description="Revises any storyboard scenes that failed enterprise brand compliance.",
    instruction=(
        "You are the Storyboard Compliance Reviser.\n"
        "If the policy critic already approved the storyboard (`policy_gate_passed`), "
        "simply confirm the approved `storyboard_id`, 3-scene table, and $10.50 cost estimate.\n"
        "Otherwise, fix every violation in `{policy_critique}` and call `save_storyboard_draft` "
        "so all 3 scenes are 100% compliant with `DOC-BRAND-01` and `DOC-PLAYBOOK-02`."
    ),
    tools=[save_storyboard_draft],
    before_model_callback=inject_creator_memory_callback,
    output_key="storyboard_draft",
)

policy_refinement_loop = LoopAgent(
    name="policy_refinement_loop",
    description="Repeats policy audit and revision until the storyboard passes all brand rules.",
    max_iterations=MAX_POLICY_PASSES,
    sub_agents=[policy_critic, storyboard_reviser],
)

storyboard_studio_pipeline = SequentialAgent(
    name="storyboard_studio_pipeline",
    description=(
        "End-to-end storyboard workflow graph: runs parallel trend + RAG ingestion, "
        "writes a 3-scene storyboard with Creator Memory, and loops through policy validation."
    ),
    sub_agents=[
        context_ingestion_fanout,
        storyboard_writer,
        policy_refinement_loop,
    ],
)


# ---------------------------------------------------------------------------
# Stage 2: Human-in-the-Loop (HITL) Sign-Off Specialist
# ---------------------------------------------------------------------------
hitl_signoff_agent = Agent(
    name="hitl_signoff_agent",
    model=MODEL,
    description=(
        "Orchestrates Human-in-the-Loop (HITL) storyboard sign-off, processes creator "
        "approvals or revision requests, and saves new creator style preferences."
    ),
    instruction=(
        "You are the Human-in-the-Loop (HITL) Production Gatekeeper for VibeStudio.\n"
        "1. When asked to submit a storyboard (e.g., `SB-1001`) for human review, call "
        "`request_creator_signoff` (a `LongRunningFunctionTool`). Present the returned "
        "`ticket_id` (e.g., `HITL-2001`), the 3-scene summary, and the `$10.50` cost "
        "clearly, and ask the creator to reply with **Approve** or **Request Revisions**.\n"
        "2. When the creator replies with an approval or revision decision for a `ticket_id`:\n"
        "   - Call `submit_creator_decision` with `decision='APPROVED'` or "
        "`decision='REVISION_REQUESTED'` and include their notes in `reviewer_notes`.\n"
        "   - If the creator also stated a standing style, lighting, audio, or aspect-ratio "
        "preference (e.g., 'I always prefer neon cyberpunk lighting'), call "
        "`save_creator_preference` so the Memory Bank remembers it for future sessions.\n"
        "   - If `decision == 'APPROVED'`, immediately transfer to `veo_production_agent` "
        "when the user wants to render keyframes and start the Veo video job."
    ),
    tools=[
        hitl_signoff_long_running_tool,
        submit_creator_decision,
        save_creator_preference,
        recall_creator_preferences,
    ],
    before_model_callback=inject_creator_memory_callback,
    after_agent_callback=evolve_creator_memory_callback,
)


# ---------------------------------------------------------------------------
# Stage 3: Long-Running Asynchronous Video Generation (Imagen 3 + Veo)
# ---------------------------------------------------------------------------
veo_production_agent = Agent(
    name="veo_production_agent",
    model=MODEL,
    description=(
        "Generates Imagen 3 scene keyframes, launches long-running asynchronous Google Veo "
        "video render jobs (`LongRunningFunctionTool`), and polls/resumes job completion."
    ),
    instruction=(
        "You are the Asynchronous Media & Veo Production Engineer for VibeStudio.\n"
        "All rendering tools are protected by `production_gate_guardrail` (`before_tool_callback`).\n"
        "1. To start video production for an approved storyboard (`SB-1001`) and HITL ticket (`HITL-2001`):\n"
        "   - First call `generate_scene_frames` with `storyboard_id`.\n"
        "   - Next call `start_veo_video_render` (`LongRunningFunctionTool`) with "
        "`storyboard_id` and `ticket_id`.\n"
        "   - Report the `PENDING` `job_id` (e.g., `VEO-3001`), `operation_name`, and "
        "keyframe URIs, explaining that the agent state is safely persisted while Veo renders.\n"
        "2. When the user asks to check status, poll, or resume a `job_id` (e.g., `VEO-3001`), "
        "call `check_or_resume_veo_job` and share the completed 3-scene clip URIs and "
        "final stitched 24-second video URI.\n"
        "3. If `production_gate_guardrail` blocks a tool call (`blocked_by_guardrail`), "
        "clearly explain which policy rule blocked it (`HITL_SIGNOFF_REQUIRED`, "
        "`HITL_NOT_APPROVED`, or `BRAND_POLICY_VIOLATION`) and guide the creator to "
        "complete HITL approval first."
    ),
    tools=[
        generate_scene_frames,
        veo_render_long_running_tool,
        check_or_resume_veo_job,
    ],
    before_tool_callback=production_gate_guardrail,
    before_model_callback=inject_creator_memory_callback,
    after_agent_callback=evolve_creator_memory_callback,
)


# ---------------------------------------------------------------------------
# Root Workflow Coordinator (`vibe_studio_director`)
# ---------------------------------------------------------------------------
root_agent = Agent(
    name="vibe_studio_director",
    model=MODEL,
    description=(
        "Executive Director for VibeStudio's automated video generation pipeline, "
        "orchestrating graph storyboarding, Enterprise RAG, Persistent Memory, "
        "Human-in-the-Loop sign-off, and asynchronous Google Veo rendering."
    ),
    instruction=(
        "You are the Executive Showrunner & Workflow Director for VibeStudio.\n"
        "Route each request to the right stage of our production graph:\n"
        "1. **New Video Concept / Storyboard Request or Revision:**\n"
        "   Delegate to `storyboard_studio_pipeline` so it runs parallel trend + Enterprise RAG "
        "research, applies Persistent Creator Memory, drafts the 3-scene 24s storyboard, and "
        "validates it through the policy loop.\n"
        "2. **Human-in-the-Loop (HITL) Review, Approval, or Style Preference Update:**\n"
        "   Delegate to `hitl_signoff_agent` whenever the user wants to pause/request sign-off "
        "on a storyboard, approve/reject a `HITL-...` ticket, or update their creator style memory.\n"
        "3. **Keyframe Generation, Asynchronous Veo Rendering, or Job Polling/Resumption:**\n"
        "   Delegate to `veo_production_agent` whenever the user asks to render frames/video "
        "(even if they try to bypass HITL!) or check/resume a `VEO-...` render job.\n"
        "4. **Inspecting or Updating Creator Memory Directly:**\n"
        "   You may also call `recall_creator_preferences` or `save_creator_preference` directly "
        "if the user asks what preferences are currently stored in the Memory Bank."
    ),
    tools=[recall_creator_preferences, save_creator_preference],
    sub_agents=[
        storyboard_studio_pipeline,
        hitl_signoff_agent,
        veo_production_agent,
    ],
    before_model_callback=inject_creator_memory_callback,
    after_agent_callback=evolve_creator_memory_callback,
)
