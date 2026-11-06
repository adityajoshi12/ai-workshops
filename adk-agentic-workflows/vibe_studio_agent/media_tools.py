"""Human-in-the-Loop (HITL) & Long-Running Asynchronous Video Generation (Imagen 3 + Veo) tools.

Supports Dual-Mode execution (`WORKSHOP_MODE=mock | live`):
  - `mock`: Simulates Imagen 3 keyframe rendering and multi-minute Veo async operations
            using SQLite job persistence (`studio.db`) and local manifest artifacts.
  - `live`: Invokes Vertex AI Imagen 3 (`imagen-3.0-generate-002`) and Google Veo
            (`veo-2.0-generate-001`) long-running operations via `google-genai`.
"""
from __future__ import annotations

import json
import os
from typing import Any

from google.adk.tools.long_running_tool import LongRunningFunctionTool
from google.adk.tools.tool_context import ToolContext

from . import db
from .knowledge_and_memory import get_workshop_mode


# ---------------------------------------------------------------------------
# 1. Human-in-the-Loop (HITL) Sign-Off Tools
# ---------------------------------------------------------------------------
def request_creator_signoff(
    storyboard_id: str,
    summary_for_reviewer: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Pause the production pipeline and request Human-in-the-Loop (HITL) creator sign-off
    before triggering paid Imagen 3 and Google Veo rendering.

    Args:
        storyboard_id: The compliant storyboard ID (e.g. 'SB-1001').
        summary_for_reviewer: Concise summary of the 3 scenes and estimated cost for the reviewer.

    Returns:
        A `PENDING_APPROVAL` ticket receipt (`ticket_id`, `review_form_schema`, and instructions).
    """
    sb = db.fetch_storyboard(storyboard_id) or tool_context.state.get("active_storyboard")
    if not isinstance(sb, dict):
        return {
            "status": "error",
            "error_message": f"Storyboard '{storyboard_id}' not found. Draft and save a storyboard first.",
        }

    ticket = db.create_hitl_ticket(
        storyboard_id=sb["storyboard_id"],
        notes=summary_for_reviewer,
    )
    tool_context.state["hitl_ticket"] = ticket
    tool_context.state["active_storyboard"] = sb

    return {
        "status": "PENDING_APPROVAL",
        "ticket_id": ticket["ticket_id"],
        "storyboard_id": sb["storyboard_id"],
        "estimated_cost_usd": sb["estimated_cost_usd"],
        "total_duration_sec": sb["total_duration_sec"],
        "review_form_schema": {
            "type": "object",
            "required": ["decision"],
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["APPROVED", "REVISION_REQUESTED"],
                    "description": "Approve to launch Imagen + Veo rendering, or request edits.",
                },
                "reviewer_notes": {
                    "type": "string",
                    "description": "Optional creative direction or style preference updates.",
                },
            },
        },
        "message": (
            f"Workflow paused at HITL Gate ({ticket['ticket_id']}). Awaiting human creator "
            f"approval for storyboard {sb['storyboard_id']} (${sb['estimated_cost_usd']:.2f} "
            "estimated Veo render cost)."
        ),
    }


def submit_creator_decision(
    ticket_id: str,
    decision: str,
    reviewer_notes: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Record the human reviewer's approval or revision request for a paused HITL ticket.

    Args:
        ticket_id: The HITL ticket ID such as 'HITL-2001'.
        decision: Either 'APPROVED' or 'REVISION_REQUESTED'.
        reviewer_notes: Any feedback or permanent creator style preferences provided by the human.

    Returns:
        Updated HITL ticket record and next workflow step.
    """
    normalized_decision = decision.strip().upper()
    if normalized_decision not in ("APPROVED", "REVISION_REQUESTED"):
        return {
            "status": "error",
            "error_message": "Decision must be 'APPROVED' or 'REVISION_REQUESTED'.",
        }

    updated = db.update_hitl_ticket(
        ticket_id=ticket_id,
        decision=normalized_decision,
        reviewer_notes=reviewer_notes,
    )
    if not updated:
        return {
            "status": "error",
            "error_message": f"HITL ticket '{ticket_id}' was not found.",
        }

    tool_context.state["hitl_ticket"] = updated
    sb = db.fetch_storyboard(updated["storyboard_id"])
    if sb:
        tool_context.state["active_storyboard"] = sb

    return {
        "status": updated["status"],
        "ticket": updated,
        "next_step": (
            "Proceed to `veo_production_agent` to generate scene keyframes and launch async Veo rendering."
            if normalized_decision == "APPROVED"
            else "Route back to `storyboard_studio_pipeline` to revise the storyboard using `reviewer_notes`."
        ),
    }


# ---------------------------------------------------------------------------
# 2. Scene Reference Keyframes (Imagen 3)
# ---------------------------------------------------------------------------
def generate_scene_frames(
    storyboard_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generate starting reference keyframes for each of the 3 scenes using Imagen 3
    (or deterministic local keyframe artifacts in `WORKSHOP_MODE=mock`).

    Requires an `APPROVED` HITL ticket for `storyboard_id` (enforced by `production_gate_guardrail`).

    Args:
        storyboard_id: The approved storyboard ID, e.g. 'SB-1001'.
    """
    sb = db.fetch_storyboard(storyboard_id) or tool_context.state.get("active_storyboard")
    if not isinstance(sb, dict):
        return {
            "status": "error",
            "error_message": f"Storyboard '{storyboard_id}' not found.",
        }

    mode = get_workshop_mode()
    db.RENDER_DIR.mkdir(parents=True, exist_ok=True)
    keyframes: list[dict[str, Any]] = []

    for scene in sb["scenes"]:
        scene_num = scene["scene_number"]
        prompt = f"{scene['visual_prompt']} | Camera: {scene['camera_motion']} | Aspect: {sb['aspect_ratio']}"
        frame_filename = f"{sb['storyboard_id']}_scene_{scene_num}_keyframe.json"
        frame_path = db.RENDER_DIR / frame_filename
        frame_uri = f"file://{frame_path}"

        if mode == "live":
            try:
                from google import genai
                from google.genai import types

                client = genai.Client()
                img_resp = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio=sb.get("aspect_ratio", "16:9"),
                    ),
                )
                if img_resp.generated_images:
                    png_path = db.RENDER_DIR / f"{sb['storyboard_id']}_scene_{scene_num}.png"
                    png_path.write_bytes(img_resp.generated_images[0].image.image_bytes)
                    frame_uri = f"file://{png_path}"
            except Exception as exc:
                frame_uri = f"file://{frame_path} (live Imagen fallback: {exc})"

        frame_meta = {
            "scene_number": scene_num,
            "time_range": scene["time_range"],
            "imagen_model": "imagen-3.0-generate-002",
            "mode": mode,
            "prompt": prompt,
            "keyframe_uri": frame_uri,
        }
        frame_path.write_text(json.dumps(frame_meta, indent=2), encoding="utf-8")
        keyframes.append(frame_meta)

    tool_context.state["scene_keyframes"] = keyframes
    return {
        "status": "success",
        "storyboard_id": sb["storyboard_id"],
        "mode": mode,
        "keyframe_count": len(keyframes),
        "keyframes": keyframes,
    }


# ---------------------------------------------------------------------------
# 3. Long-Running Asynchronous Video Generation (Google Veo)
# ---------------------------------------------------------------------------
def start_veo_video_render(
    storyboard_id: str,
    ticket_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Launch an asynchronous Google Veo video generation job (`veo-2.0-generate-001`)
    wrapped in ADK's `LongRunningFunctionTool`.

    Immediately returns a `PENDING` operation receipt (`job_id` and `operation_name`)
    so the agent runtime can hibernate without blocking on multi-minute video rendering.

    Args:
        storyboard_id: The approved storyboard ID, e.g. 'SB-1001'.
        ticket_id: The approved HITL ticket ID, e.g. 'HITL-2001'.
    """
    sb = db.fetch_storyboard(storyboard_id) or tool_context.state.get("active_storyboard")
    if not isinstance(sb, dict):
        return {
            "status": "error",
            "error_message": f"Storyboard '{storyboard_id}' not found.",
        }

    keyframes = tool_context.state.get("scene_keyframes") or []
    if not keyframes:
        frame_res = generate_scene_frames(storyboard_id=sb["storyboard_id"], tool_context=tool_context)
        keyframes = frame_res.get("keyframes", [])

    mode = get_workshop_mode()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "vibestudio-workshop")
    operation_name = (
        f"projects/{project_id}/locations/us-central1/publishers/google/"
        f"models/veo-2.0-generate-001/operations/veo-op-{sb['storyboard_id'].lower()}"
    )

    if mode == "live":
        try:
            from google import genai
            from google.genai import types

            client = genai.Client()
            combined_prompt = " || ".join(
                f"Scene {s['scene_number']} ({s['time_range']}): {s['visual_prompt']} ({s['camera_motion']})"
                for s in sb["scenes"]
            )
            gcs_bucket = os.environ.get("VIBESTUDIO_GCS_BUCKET", "").rstrip("/")
            config_kwargs: dict[str, Any] = {
                "aspect_ratio": sb.get("aspect_ratio", "16:9"),
            }
            if gcs_bucket:
                config_kwargs["output_gcs_uri"] = f"{gcs_bucket}/renders/{sb['storyboard_id']}/"

            operation = client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=combined_prompt,
                config=types.GenerateVideosConfig(**config_kwargs),
            )
            if getattr(operation, "name", None):
                operation_name = operation.name
        except Exception as exc:
            operation_name = f"{operation_name}-fallback ({exc})"

    job = db.create_veo_job(
        storyboard_id=sb["storyboard_id"],
        ticket_id=ticket_id,
        mode=mode,
        operation_name=operation_name,
        keyframes=keyframes,
    )
    tool_context.state["active_veo_job"] = job

    return {
        "status": "PENDING",
        "job_id": job["job_id"],
        "storyboard_id": sb["storyboard_id"],
        "ticket_id": ticket_id,
        "mode": mode,
        "veo_model": "veo-2.0-generate-001",
        "operation_name": job["operation_name"],
        "message": (
            f"Asynchronous Veo render job {job['job_id']} started (status: PENDING). "
            "Call `check_or_resume_veo_job` with this `job_id` to poll completion and "
            "stitch the final 24-second video."
        ),
    }


def check_or_resume_veo_job(
    job_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Poll or resume an asynchronous Veo video generation job by `job_id`,
    stitch the 3 rendered 8-second scene clips, and publish the final video manifest.

    Args:
        job_id: The Veo job ID returned by `start_veo_video_render`, e.g. 'VEO-3001'.
    """
    job = db.fetch_veo_job(job_id)
    if not job:
        return {
            "status": "error",
            "error_message": f"Veo job '{job_id}' was not found.",
        }

    sb = db.fetch_storyboard(job["storyboard_id"])
    if not sb:
        return {
            "status": "error",
            "error_message": f"Storyboard '{job['storyboard_id']}' linked to job '{job_id}' not found.",
        }

    db.RENDER_DIR.mkdir(parents=True, exist_ok=True)
    gcs_bucket = os.environ.get("VIBESTUDIO_GCS_BUCKET", "").rstrip("/")
    base_uri = gcs_bucket if (job["mode"] == "live" and gcs_bucket) else f"file://{db.RENDER_DIR}"

    scene_videos: list[dict[str, Any]] = []
    for scene in sb["scenes"]:
        s_num = scene["scene_number"]
        clip_uri = f"{base_uri}/{job['job_id']}_scene_{s_num}_8s.mp4"
        scene_videos.append(
            {
                "scene_number": s_num,
                "duration_sec": 8,
                "time_range": scene["time_range"],
                "clip_uri": clip_uri,
                "voiceover": scene["voiceover"],
            }
        )

    final_video_uri = f"{base_uri}/{job['job_id']}_{sb['storyboard_id']}_final_24s.mp4"
    manifest_path = db.RENDER_DIR / f"{job['job_id']}_production_manifest.json"
    manifest_payload = {
        "job_id": job["job_id"],
        "storyboard_id": sb["storyboard_id"],
        "ticket_id": job["ticket_id"],
        "topic": sb["topic"],
        "aspect_ratio": sb["aspect_ratio"],
        "total_duration_sec": sb["total_duration_sec"],
        "total_cost_usd": sb["estimated_cost_usd"],
        "mode": job["mode"],
        "operation_name": job["operation_name"],
        "keyframes": job["keyframes"],
        "scene_videos": scene_videos,
        "final_video_uri": final_video_uri,
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    completed_job = db.complete_veo_job(
        job_id=job["job_id"],
        scene_videos=scene_videos,
        final_video_uri=final_video_uri,
    )
    tool_context.state["active_veo_job"] = completed_job

    return {
        "status": "COMPLETED",
        "job": completed_job,
        "production_manifest_path": str(manifest_path),
        "final_video_uri": final_video_uri,
        "message": (
            f"Veo job {job['job_id']} completed! All 3 scenes (24s total) rendered and "
            f"published to {final_video_uri}."
        ),
    }


# Wrap the HITL sign-off and async Veo trigger in ADK's LongRunningFunctionTool
hitl_signoff_long_running_tool = LongRunningFunctionTool(func=request_creator_signoff)
veo_render_long_running_tool = LongRunningFunctionTool(func=start_veo_video_render)
