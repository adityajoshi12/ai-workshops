"""Enterprise Knowledge Base (RAG) & Persistent Memory Bank tools for VibeStudio.

Supports Dual-Mode execution (`WORKSHOP_MODE=mock | live`):
  - `mock`: Queries local SQLite-indexed Markdown corpus (`brand_guidelines.md`,
            `production_playbook.md`, `audience_insights.md`) and SQLite Memory Bank.
  - `live`: Queries Vertex AI RAG Engine (`VERTEX_RAG_CORPUS_NAME`) when configured,
            with automatic fallback to the local SQLite corpus.
"""
from __future__ import annotations

import os
from typing import Any

from google.adk.tools.tool_context import ToolContext

from . import db


def get_workshop_mode() -> str:
    return os.environ.get("WORKSHOP_MODE", "mock").strip().lower()


# ---------------------------------------------------------------------------
# 1. Enterprise Knowledge Base (RAG) Tool
# ---------------------------------------------------------------------------
def search_enterprise_knowledge(
    query: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Query the VibeStudio Enterprise Knowledge Base (RAG Engine) for brand guidelines,
    production rules, banned tropes, and audience retention insights.

    Args:
        query: Search query such as 'brand safety banned tropes 24s scene structure'.

    Returns:
        Dict with matched knowledge chunks, source document IDs, and mandatory production rules.
    """
    mode = get_workshop_mode()
    rag_corpus = os.environ.get("VERTEX_RAG_CORPUS_NAME", "").strip()
    vertex_snippets: list[dict[str, Any]] = []

    if mode == "live" and rag_corpus:
        try:
            from vertexai.preview import rag  # type: ignore[import-untyped]

            response = rag.retrieval_query(
                rag_resources=[rag.RagResource(rag_corpus=rag_corpus)],
                text=query,
                similarity_top_k=3,
            )
            for ctx in getattr(response.contexts, "contexts", []):
                vertex_snippets.append(
                    {
                        "source": getattr(ctx, "source_uri", rag_corpus),
                        "text": getattr(ctx, "text", ""),
                    }
                )
        except Exception as exc:
            vertex_snippets.append(
                {
                    "source": "vertex_rag_fallback_notice",
                    "text": f"Vertex AI RAG fallback to local SQLite index: {exc}",
                }
            )

    local_chunks = db.search_knowledge_chunks(query=query, top_k=4)
    payload = {
        "status": "success",
        "mode": "live_vertex_rag" if (mode == "live" and rag_corpus) else "local_sqlite_rag",
        "query": query,
        "matched_chunks": local_chunks,
        "vertex_rag_contexts": vertex_snippets,
        "mandatory_rules": {
            "target_scene_count": db.TARGET_SCENE_COUNT,
            "scene_duration_sec": db.SCENE_DURATION_SEC,
            "max_total_duration_sec": db.TARGET_SCENE_COUNT * db.SCENE_DURATION_SEC,
            "scene_cost_usd": db.SCENE_COST_USD,
            "max_budget_usd": db.MAX_BUDGET_USD,
            "banned_tropes": db.BANNED_TROPES,
        },
    }
    tool_context.state["enterprise_knowledge"] = payload
    return payload


# ---------------------------------------------------------------------------
# 2. Persistent Memory Bank Tools
# ---------------------------------------------------------------------------
def recall_creator_preferences(
    tool_context: ToolContext,
    creator_id: str = "creator-default",
) -> dict[str, Any]:
    """Load persistent creator preferences (visual style, audio, aspect ratio) from the Memory Bank.

    Args:
        creator_id: Creator profile identifier, defaults to 'creator-default'.

    Returns:
        Dict containing all stored long-term creator preferences.
    """
    memories = db.list_creator_memories(creator_id=creator_id)
    summary_lines = [
        f"- [{m['category']}] {m['preference']} (source: {m['source']})"
        for m in memories
    ]
    formatted = "\n".join(summary_lines) if summary_lines else "No stored creator preferences."
    tool_context.state["creator_memory_context"] = formatted
    tool_context.state["creator_memories"] = memories
    return {
        "status": "success",
        "creator_id": creator_id,
        "memory_count": len(memories),
        "preferences": memories,
        "formatted_context": formatted,
    }


def save_creator_preference(
    category: str,
    preference: str,
    tool_context: ToolContext,
    creator_id: str = "creator-default",
) -> dict[str, Any]:
    """Save or evolve a persistent creator preference in the long-term Memory Bank.

    Call this whenever the creator expresses a standing style, lighting, audio,
    pacing, or aspect-ratio preference so future video runs remember it automatically.

    Args:
        category: Category key such as 'visual_style', 'audio_and_pacing',
            'aspect_ratio', or 'lighting_preference'.
        preference: Clear description of the creator's preference.
        creator_id: Creator identifier, defaults to 'creator-default'.

    Returns:
        The persisted memory record and updated memory bank snapshot.
    """
    record = db.upsert_creator_memory(
        category=category.strip().lower(),
        preference=preference.strip(),
        creator_id=creator_id,
        source="explicit_tool_save",
    )
    all_memories = db.list_creator_memories(creator_id=creator_id)
    tool_context.state["creator_memories"] = all_memories
    tool_context.state["creator_memory_context"] = "\n".join(
        f"- [{m['category']}] {m['preference']}" for m in all_memories
    )
    return {
        "status": "saved_to_memory_bank",
        "saved_memory": record,
        "total_memories": len(all_memories),
    }


# ---------------------------------------------------------------------------
# 3. Storyboard Persistence & Policy Loop Gate Tools
# ---------------------------------------------------------------------------
def save_storyboard_draft(
    topic: str,
    scene_1_visual_prompt: str,
    scene_1_camera_motion: str,
    scene_1_voiceover: str,
    scene_2_visual_prompt: str,
    scene_2_camera_motion: str,
    scene_2_voiceover: str,
    scene_3_visual_prompt: str,
    scene_3_camera_motion: str,
    scene_3_voiceover: str,
    tool_context: ToolContext,
    aspect_ratio: str = "16:9",
) -> dict[str, Any]:
    """Persist a 3-scene (24-second) storyboard draft to SQLite and session state,
    and run an automatic brand & budget compliance audit.

    Args:
        topic: High-level video topic or brief.
        scene_1_visual_prompt: Visual description & lighting for Scene 1 (0-8s Hook).
        scene_1_camera_motion: Camera movement for Scene 1 (e.g. '35mm slow dolly-in').
        scene_1_voiceover: Narration script for Scene 1 (12-22 words).
        scene_2_visual_prompt: Visual description & lighting for Scene 2 (8-16s Core Turn).
        scene_2_camera_motion: Camera movement for Scene 2 (e.g. 'tracking shot').
        scene_2_voiceover: Narration script for Scene 2 (12-22 words).
        scene_3_visual_prompt: Visual description & lighting for Scene 3 (16-24s Payoff).
        scene_3_camera_motion: Camera movement for Scene 3 (e.g. 'golden hour hero orbit').
        scene_3_voiceover: Narration script for Scene 3 (12-22 words).
        aspect_ratio: '16:9' or '9:16'.

    Returns:
        Saved storyboard record including `storyboard_id`, `estimated_cost_usd`,
        `policy_status` ('COMPLIANT' or 'VIOLATION'), and any `violations`.
    """
    scenes = [
        {
            "scene_number": 1,
            "time_range": "0s-8s",
            "duration_sec": 8,
            "role": "The Visual Hook",
            "visual_prompt": scene_1_visual_prompt,
            "camera_motion": scene_1_camera_motion,
            "voiceover": scene_1_voiceover,
        },
        {
            "scene_number": 2,
            "time_range": "8s-16s",
            "duration_sec": 8,
            "role": "The Core Mechanism",
            "visual_prompt": scene_2_visual_prompt,
            "camera_motion": scene_2_camera_motion,
            "voiceover": scene_2_voiceover,
        },
        {
            "scene_number": 3,
            "time_range": "16s-24s",
            "duration_sec": 8,
            "role": "The Payoff",
            "visual_prompt": scene_3_visual_prompt,
            "camera_motion": scene_3_camera_motion,
            "voiceover": scene_3_voiceover,
        },
    ]
    existing_sb = tool_context.state.get("active_storyboard")
    existing_id = existing_sb.get("storyboard_id") if isinstance(existing_sb, dict) else None

    saved = db.save_storyboard(
        topic=topic,
        scenes=scenes,
        aspect_ratio=aspect_ratio,
        storyboard_id=existing_id,
    )
    tool_context.state["active_storyboard"] = saved
    return saved


def evaluate_brand_compliance(
    storyboard_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Run deterministic policy, banned-trope, scene-duration, and budget checks on a storyboard.

    Args:
        storyboard_id: Storyboard ID such as 'SB-1001'.

    Returns:
        Compliance status ('COMPLIANT' or 'VIOLATION') and detailed findings.
    """
    sb = db.fetch_storyboard(storyboard_id)
    if not sb:
        active = tool_context.state.get("active_storyboard")
        if isinstance(active, dict):
            sb = active
    if not sb:
        return {
            "status": "error",
            "error_message": f"Storyboard '{storyboard_id}' not found. Call `save_storyboard_draft` first.",
        }

    audit = db.evaluate_storyboard_compliance(
        scenes=sb["scenes"],
        aspect_ratio=sb.get("aspect_ratio", "16:9"),
    )
    tool_context.state["policy_audit"] = audit
    return {
        "status": "success",
        "storyboard_id": sb["storyboard_id"],
        **audit,
    }


def approve_policy_gate(
    storyboard_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Signal that the storyboard passed all enterprise brand & budget checks and exit the refinement loop.

    Call this ONLY when `evaluate_brand_compliance` returns `policy_status == 'COMPLIANT'`.

    Args:
        storyboard_id: The compliant storyboard ID, e.g. 'SB-1001'.
    """
    sb = db.fetch_storyboard(storyboard_id) or tool_context.state.get("active_storyboard")
    if isinstance(sb, dict) and sb.get("policy_status") == "VIOLATION":
        return {
            "status": "blocked",
            "message": (
                f"Cannot exit policy loop: storyboard {storyboard_id} still has "
                f"violations: {sb.get('violations')}"
            ),
        }

    # Break out of the enclosing ADK LoopAgent deterministically
    tool_context.actions.escalate = True
    tool_context.state["policy_gate_passed"] = True
    return {
        "status": "policy_approved",
        "storyboard_id": storyboard_id,
        "message": "Storyboard passed enterprise policy checks. Ready for Human-in-the-Loop sign-off.",
    }
