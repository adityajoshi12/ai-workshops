"""Lifecycle & Guardrail Callbacks for VibeStudio Agentic Workflow.

Implements three core ADK callback patterns:
  1. `inject_creator_memory_callback` (`before_model_callback`):
     Loads long-term creator preferences from the Memory Bank before each LLM call
     and injects them into session state and model system instructions.
  2. `evolve_creator_memory_callback` (`after_agent_callback`):
     Inspects user feedback and HITL review notes after agent turns to automatically
     evolve persistent creator preferences in the Memory Bank.
  3. `production_gate_guardrail` (`before_tool_callback`):
     Deterministically blocks expensive Imagen 3 / Veo rendering tools unless the
     storyboard is `COMPLIANT` and has an `APPROVED` Human-in-the-Loop ticket.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from . import db

_PREFERENCE_PATTERNS = [
    (
        "visual_style",
        re.compile(
            r"(?:i\s+always\s+prefer|always\s+use|remember\s+i\s+like|my\s+style\s+is|prefer\s+visual\s+style)\s+([^.!?\n]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "lighting_preference",
        re.compile(
            r"(?:lighting\s+preference|always\s+light\s+with|use\s+lighting)\s*:?\s*([^.!?\n]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "aspect_ratio",
        re.compile(
            r"(?:default\s+to|always\s+render\s+in|prefer\s+aspect\s+ratio)\s+(9:16|16:9)([^.!?\n]*)",
            re.IGNORECASE,
        ),
    ),
]


# ---------------------------------------------------------------------------
# 1. before_model_callback — Inject Persistent Memory Bank Context
# ---------------------------------------------------------------------------
def inject_creator_memory_callback(
    callback_context: CallbackContext,
    llm_request: Any,
) -> Optional[Any]:
    """Load persistent creator preferences from the Memory Bank into state and prompt."""
    memories = db.list_creator_memories(creator_id="creator-default")
    formatted = "\n".join(
        f"- [{m['category']}] {m['preference']} (source: {m['source']})"
        for m in memories
    )
    callback_context.state["creator_memory_context"] = formatted
    callback_context.state["creator_memories"] = memories

    # Also append the Memory Bank block into the outgoing LLM system instruction
    config = getattr(llm_request, "config", None)
    if config is not None:
        current_sys = getattr(config, "system_instruction", None) or ""
        marker = "[PERSISTENT CREATOR MEMORY BANK]"
        if isinstance(current_sys, str) and marker not in current_sys:
            config.system_instruction = (
                f"{current_sys}\n\n{marker}\n{formatted}\n"
                "Always honor these persistent creator preferences when planning or writing scenes."
            )
    return None


# ---------------------------------------------------------------------------
# 2. after_agent_callback — Evolve Persistent Memory Bank from Feedback
# ---------------------------------------------------------------------------
def extract_and_persist_preferences_from_text(
    text: str,
    source: str = "after_agent_callback",
) -> list[dict[str, Any]]:
    """Extract standing creator preferences from user text or HITL reviewer notes."""
    saved: list[dict[str, Any]] = []
    if not text:
        return saved

    for category, pattern in _PREFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            pref_value = " ".join(g.strip() for g in match.groups() if g and g.strip())
            record = db.upsert_creator_memory(
                category=category,
                preference=pref_value,
                creator_id="creator-default",
                source=source,
            )
            saved.append(record)
    return saved


def evolve_creator_memory_callback(
    callback_context: CallbackContext,
) -> Optional[Any]:
    """Automatically extract new creator preferences after an agent turn and persist them."""
    # Check HITL reviewer notes in session state if present
    ticket = callback_context.state.get("hitl_ticket")
    if isinstance(ticket, dict) and ticket.get("reviewer_notes"):
        extract_and_persist_preferences_from_text(
            str(ticket["reviewer_notes"]),
            source="hitl_reviewer_notes_callback",
        )

    # Inspect latest user event in session history if accessible
    inv_ctx = getattr(callback_context, "_invocation_context", None)
    session = getattr(callback_context, "session", None) or getattr(inv_ctx, "session", None)
    events = getattr(session, "events", None) or []
    for event in reversed(events):
        if getattr(event, "author", "") == "user":
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    extract_and_persist_preferences_from_text(
                        part_text,
                        source="after_agent_callback",
                    )
            break

    # Refresh state snapshot
    memories = db.list_creator_memories(creator_id="creator-default")
    callback_context.state["creator_memories"] = memories
    callback_context.state["creator_memory_context"] = "\n".join(
        f"- [{m['category']}] {m['preference']}" for m in memories
    )
    return None


# ---------------------------------------------------------------------------
# 3. before_tool_callback — Deterministic HITL & Brand Policy Guardrail
# ---------------------------------------------------------------------------
def production_gate_guardrail(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict[str, Any]]:
    """Deterministic guardrail protecting `generate_scene_frames` and `start_veo_video_render`.

    Returns `None` to allow tool execution, or returns a dict to short-circuit and block it.
    """
    protected_tools = {"generate_scene_frames", "start_veo_video_render"}
    if tool.name not in protected_tools:
        return None

    storyboard_id = str(args.get("storyboard_id", "")).strip().upper()
    sb = db.fetch_storyboard(storyboard_id) if storyboard_id else None
    if not sb:
        active_sb = tool_context.state.get("active_storyboard")
        if isinstance(active_sb, dict) and (
            not storyboard_id or active_sb.get("storyboard_id") == storyboard_id
        ):
            sb = active_sb

    # Rule 1: Storyboard must exist
    if not sb:
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "MISSING_STORYBOARD",
            "error_message": (
                f"Guardrail blocked `{tool.name}`: Storyboard '{storyboard_id}' does not exist "
                "in Studio DB. Run the storyboard pipeline (`save_storyboard_draft`) first."
            ),
        }

    # Rule 2: Storyboard must pass enterprise brand & budget compliance
    if sb.get("policy_status") != "COMPLIANT":
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "BRAND_POLICY_VIOLATION",
            "storyboard_id": sb["storyboard_id"],
            "violations": sb.get("violations", []),
            "error_message": (
                f"Guardrail blocked `{tool.name}`: Storyboard {sb['storyboard_id']} has "
                f"unresolved brand/budget violations: {sb.get('violations')}. "
                "Revise the storyboard before rendering."
            ),
        }

    # Rule 3: Storyboard must have an APPROVED Human-in-the-Loop (HITL) ticket
    requested_ticket_id = str(args.get("ticket_id", "")).strip().upper()
    ticket = (
        db.fetch_hitl_ticket(requested_ticket_id)
        if requested_ticket_id
        else db.fetch_latest_hitl_for_storyboard(sb["storyboard_id"])
    )

    if not ticket:
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "HITL_SIGNOFF_REQUIRED",
            "storyboard_id": sb["storyboard_id"],
            "error_message": (
                f"Guardrail blocked `{tool.name}`: No Human-in-the-Loop ticket exists for "
                f"storyboard {sb['storyboard_id']}. Call `request_creator_signoff` first "
                f"to obtain creator approval for the ${sb['estimated_cost_usd']:.2f} render."
            ),
        }

    if ticket.get("status") != "APPROVED" or ticket.get("storyboard_id") != sb["storyboard_id"]:
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "HITL_NOT_APPROVED",
            "storyboard_id": sb["storyboard_id"],
            "ticket_id": ticket.get("ticket_id"),
            "ticket_status": ticket.get("status"),
            "error_message": (
                f"Guardrail blocked `{tool.name}`: HITL ticket {ticket.get('ticket_id')} "
                f"for storyboard {sb['storyboard_id']} has status '{ticket.get('status')}' "
                "(must be 'APPROVED'). Wait for human approval via `submit_creator_decision`."
            ),
        }

    return None
