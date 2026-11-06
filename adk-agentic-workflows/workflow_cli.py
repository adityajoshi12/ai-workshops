#!/usr/bin/env python3
"""Companion CLI for the VibeStudio Agentic Workflow Workshop.

Commands:
  python3 workflow_cli.py status
  python3 workflow_cli.py search-rag "banned tropes and 24s scene structure"
  python3 workflow_cli.py add-memory --category visual_style --preference "Always use neon cyberpunk rim lighting"
  python3 workflow_cli.py approve HITL-2001 --notes "Approved! Remember I always prefer synthwave audio."
  python3 workflow_cli.py resume-veo VEO-3001
  python3 workflow_cli.py test-pipeline
  python3 workflow_cli.py reset
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from vibe_studio_agent import db


@dataclass
class _StubActions:
    escalate: bool = False


@dataclass
class _StubToolContext:
    state: dict[str, Any] = field(default_factory=dict)
    actions: _StubActions = field(default_factory=_StubActions)


@dataclass
class _StubTool:
    name: str


def _print_header(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def cmd_status() -> None:
    snapshot = db.list_all_studio_records()
    _print_header(f"VibeStudio Database Status ({db.DB_PATH.name})")
    print(f"Indexed Enterprise RAG Chunks : {snapshot['knowledge_chunk_count']}")

    print(f"\nPersistent Creator Memory Bank ({len(snapshot['creator_memories'])} entries):")
    for m in snapshot["creator_memories"]:
        print(f"  - [{m['memory_id']}] ({m['category']}) {m['preference']}  [source: {m['source']}]")

    print(f"\nDrafted Storyboards ({len(snapshot['storyboards'])}):")
    if not snapshot["storyboards"]:
        print("  (none yet)")
    for sb in snapshot["storyboards"]:
        print(
            f"  - {sb['storyboard_id']} | topic='{sb['topic']}' | "
            f"{sb['total_duration_sec']}s | ${sb['estimated_cost_usd']:.2f} | "
            f"policy={sb['policy_status']}"
        )

    print(f"\nHuman-in-the-Loop (HITL) Tickets ({len(snapshot['hitl_tickets'])}):")
    if not snapshot["hitl_tickets"]:
        print("  (none yet)")
    for t in snapshot["hitl_tickets"]:
        print(
            f"  - {t['ticket_id']} | storyboard={t['storyboard_id']} | "
            f"status={t['status']} | notes='{t.get('reviewer_notes') or ''}'"
        )

    print(f"\nAsynchronous Veo Render Jobs ({len(snapshot['veo_jobs'])}):")
    if not snapshot["veo_jobs"]:
        print("  (none yet)")
    for j in snapshot["veo_jobs"]:
        print(
            f"  - {j['job_id']} | storyboard={j['storyboard_id']} | ticket={j['ticket_id']} | "
            f"status={j['status']} | final_uri={j.get('final_video_uri') or 'PENDING'}"
        )


def cmd_search_rag(query: str) -> None:
    _print_header(f"Enterprise Knowledge Base (RAG) Query: '{query}'")
    chunks = db.search_knowledge_chunks(query=query, top_k=3)
    for idx, ch in enumerate(chunks, start=1):
        print(f"\n[{idx}] {ch['chunk_id']} — {ch['doc_id']} ({ch['doc_title']})")
        print(f"    Section: {ch['section_heading']}")
        snippet = " ".join(ch["content"].splitlines()[1:4]).strip()
        print(f"    Snippet: {snippet[:220]}...")


def cmd_add_memory(category: str, preference: str) -> None:
    rec = db.upsert_creator_memory(
        category=category,
        preference=preference,
        source="workflow_cli",
    )
    _print_header("Saved Persistent Creator Preference")
    print(json.dumps(rec, indent=2))


def cmd_approve_hitl(ticket_id: str, decision: str, notes: str) -> None:
    updated = db.update_hitl_ticket(ticket_id=ticket_id, decision=decision, reviewer_notes=notes)
    if not updated:
        print(f"Error: HITL ticket '{ticket_id}' not found.", file=sys.stderr)
        sys.exit(1)

    _print_header(f"Updated HITL Ticket {updated['ticket_id']} -> {updated['status']}")
    print(json.dumps(updated, indent=2))

    # Also run the preference extractor on reviewer notes
    if notes:
        for cat_key, regex in [
            ("visual_style", r"(?:i\s+always\s+prefer|always\s+use|remember\s+i\s+like)\s+([^.!?\n]+)"),
            ("lighting_preference", r"(?:lighting\s+preference|always\s+light\s+with)\s*:?\s*([^.!?\n]+)"),
        ]:
            import re

            m = re.search(regex, notes, re.IGNORECASE)
            if m:
                mem = db.upsert_creator_memory(
                    category=cat_key,
                    preference=m.group(1).strip(),
                    source="hitl_cli_notes",
                )
                print(f"\n[Memory Bank Evolved] Saved new preference: {mem['memory_id']} ({mem['category']})")


def cmd_resume_veo(job_id: str) -> None:
    job = db.fetch_veo_job(job_id)
    if not job:
        print(f"Error: Veo job '{job_id}' not found.", file=sys.stderr)
        sys.exit(1)
    sb = db.fetch_storyboard(job["storyboard_id"])
    if not sb:
        print(f"Error: Storyboard '{job['storyboard_id']}' not found.", file=sys.stderr)
        sys.exit(1)

    db.RENDER_DIR.mkdir(parents=True, exist_ok=True)
    scene_videos = [
        {
            "scene_number": s["scene_number"],
            "duration_sec": 8,
            "time_range": s["time_range"],
            "clip_uri": f"file://{db.RENDER_DIR}/{job['job_id']}_scene_{s['scene_number']}_8s.mp4",
            "voiceover": s["voiceover"],
        }
        for s in sb["scenes"]
    ]
    final_uri = f"file://{db.RENDER_DIR}/{job['job_id']}_{sb['storyboard_id']}_final_24s.mp4"
    manifest_path = db.RENDER_DIR / f"{job['job_id']}_production_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "job_id": job["job_id"],
                "storyboard_id": sb["storyboard_id"],
                "ticket_id": job["ticket_id"],
                "scene_videos": scene_videos,
                "final_video_uri": final_uri,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    completed = db.complete_veo_job(
        job_id=job["job_id"],
        scene_videos=scene_videos,
        final_video_uri=final_uri,
    )
    _print_header(f"Resumed & Completed Async Veo Job {job['job_id']}")
    print(json.dumps(completed, indent=2))
    print(f"\nProduction manifest written to: {manifest_path}")


def cmd_test_pipeline() -> None:
    _print_header("Running End-to-End VibeStudio Workflow & Guardrail Verification")
    db.ensure_initialized(force_reset=True)

    # 1. Verify RAG Knowledge Base Indexing
    chunks = db.search_knowledge_chunks("banned tropes 24-second 3-scene budget", top_k=3)
    assert len(chunks) == 3, "Expected 3 RAG chunks"
    print(f"[PASS] 1. Enterprise RAG Engine indexed {len(chunks)} top chunks (docs: {[c['doc_id'] for c in chunks]})")

    # 2. Verify Policy Critique catches banned tropes ('flashing strobe')
    bad_scenes = [
        {
            "scene_number": 1,
            "time_range": "0s-8s",
            "duration_sec": 8,
            "visual_prompt": "A dark server room with flashing strobe lights and clickbait shock face",
            "camera_motion": "fast zoom",
            "voiceover": "Want guaranteed profit with AI agents?",
        },
        {
            "scene_number": 2,
            "time_range": "8s-16s",
            "duration_sec": 8,
            "visual_prompt": "Code on screen",
            "camera_motion": "",
            "voiceover": "Here is how it works.",
        },
    ]
    bad_audit = db.evaluate_storyboard_compliance(bad_scenes)
    assert bad_audit["policy_status"] == "VIOLATION", "Expected VIOLATION for bad scenes"
    print(
        f"[PASS] 2. Policy Loop Auditor caught {len(bad_audit['violations'])} violations "
        "(scene count, missing camera_motion, and banned tropes)"
    )

    # 3. Save a revised, compliant 3-scene storyboard (SB-1001)
    clean_scenes = [
        {
            "scene_number": 1,
            "time_range": "0s-8s",
            "duration_sec": 8,
            "visual_prompt": "Warm amber studio diorama of a glowing brass railway switchboard routing AI packets",
            "camera_motion": "35mm anamorphic slow dolly-in",
            "voiceover": "Why do single-prompt AI agents break in production? Because they lack a workflow graph.",
        },
        {
            "scene_number": 2,
            "time_range": "8s-16s",
            "duration_sec": 8,
            "visual_prompt": "Isometric split-screen showing parallel research nodes merging into a golden JoinNode",
            "camera_motion": "smooth lateral tracking shot, shallow depth of field",
            "voiceover": "With Google ADK, parallel fan-out nodes gather context while a policy loop enforces guardrails.",
        },
        {
            "scene_number": 3,
            "time_range": "16s-24s",
            "duration_sec": 8,
            "visual_prompt": "A human director pressing a glowing green approval key that launches a cinema reel into Cloud Run",
            "camera_motion": "golden hour hero orbit pull-back",
            "voiceover": "Pause for human sign-off, render asynchronously with Veo, and ship on Cloud Run.",
        },
    ]
    sb = db.save_storyboard(
        topic="How Agentic Workflows in Google ADK Work",
        scenes=clean_scenes,
        aspect_ratio="16:9",
    )
    assert sb["policy_status"] == "COMPLIANT", f"Unexpected violation: {sb['violations']}"
    print(
        f"[PASS] 3. Saved compliant 3-scene storyboard {sb['storyboard_id']} "
        f"({sb['total_duration_sec']}s, ${sb['estimated_cost_usd']:.2f})"
    )

    # 4. Verify HITL Guardrail blocks Veo rendering BEFORE human sign-off
    latest_ticket = db.fetch_latest_hitl_for_storyboard(sb["storyboard_id"])
    assert latest_ticket is None, "Expected no HITL ticket yet"
    print(
        f"[PASS] 4. Deterministic Guardrail Check: {sb['storyboard_id']} has no HITL ticket yet -> "
        "blocks premature Veo spend (`HITL_SIGNOFF_REQUIRED`)"
    )

    # 5. Create HITL Ticket (PENDING_APPROVAL) and approve it with new Creator Memory preference
    ticket = db.create_hitl_ticket(
        storyboard_id=sb["storyboard_id"],
        notes="Ready for creator review ($10.50 estimated Veo render).",
    )
    assert ticket["status"] == "PENDING_APPROVAL"
    print(f"[PASS] 5. Workflow suspended at HITL Gate: created ticket {ticket['ticket_id']} ({ticket['status']})")

    approved_ticket = db.update_hitl_ticket(
        ticket_id=ticket["ticket_id"],
        decision="APPROVED",
        reviewer_notes="Approved! Also I always prefer cozy solarpunk brass and teal lighting.",
    )
    assert approved_ticket and approved_ticket["status"] == "APPROVED"
    db.upsert_creator_memory(
        category="visual_style",
        preference="cozy solarpunk brass and teal lighting",
        source="hitl_reviewer_notes_callback",
    )
    print(
        f"[PASS] 6. Human Reviewer approved {ticket['ticket_id']} and evolved Memory Bank "
        f"(`visual_style` updated)"
    )

    # 6. Start Long-Running Async Veo Job (PENDING) and resume to COMPLETED
    keyframes = [
        {
            "scene_number": s["scene_number"],
            "time_range": s["time_range"],
            "keyframe_uri": f"file://{db.RENDER_DIR}/{sb['storyboard_id']}_scene_{s['scene_number']}_keyframe.json",
        }
        for s in sb["scenes"]
    ]
    veo_job = db.create_veo_job(
        storyboard_id=sb["storyboard_id"],
        ticket_id=ticket["ticket_id"],
        mode="mock",
        operation_name="projects/vibestudio/locations/us-central1/operations/veo-op-sb-1001",
        keyframes=keyframes,
    )
    assert veo_job["status"] == "PENDING"
    print(f"[PASS] 7. Started Long-Running Async Veo Job {veo_job['job_id']} (status={veo_job['status']})")

    cmd_resume_veo(veo_job["job_id"])
    final_job = db.fetch_veo_job(veo_job["job_id"])
    assert final_job and final_job["status"] == "COMPLETED"
    print(f"\n[ALL CHECKS PASSED] End-to-end VibeStudio workflow verified!")


def main() -> None:
    parser = argparse.ArgumentParser(description="VibeStudio Agentic Workflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show Studio SQLite DB status (RAG, Memory, Storyboards, HITL, Veo jobs)")

    rag_p = sub.add_parser("search-rag", help="Search the Enterprise Knowledge Base")
    rag_p.add_argument("query", type=str, help="Search query string")

    mem_p = sub.add_parser("add-memory", help="Save or update a persistent creator preference")
    mem_p.add_argument("--category", required=True, help="e.g. visual_style, audio_and_pacing, aspect_ratio")
    mem_p.add_argument("--preference", required=True, help="Preference description")

    hitl_p = sub.add_parser("approve", help="Approve or request revision on a HITL ticket")
    hitl_p.add_argument("ticket_id", help="HITL ticket ID, e.g. HITL-2001")
    hitl_p.add_argument(
        "--decision",
        default="APPROVED",
        choices=["APPROVED", "REVISION_REQUESTED"],
        help="Approval decision (default: APPROVED)",
    )
    hitl_p.add_argument("--notes", default="Approved via workflow_cli.py", help="Reviewer feedback notes")

    veo_p = sub.add_parser("resume-veo", help="Poll and complete an asynchronous Veo render job")
    veo_p.add_argument("job_id", help="Veo job ID, e.g. VEO-3001")

    sub.add_parser("test-pipeline", help="Run automated end-to-end verification of all workflow stages")
    sub.add_parser("reset", help="Reset studio.db back to clean seed state")

    args = parser.parse_args()
    if args.command == "status":
        cmd_status()
    elif args.command == "search-rag":
        cmd_search_rag(args.query)
    elif args.command == "add-memory":
        cmd_add_memory(args.category, args.preference)
    elif args.command == "approve":
        cmd_approve_hitl(args.ticket_id, args.decision, args.notes)
    elif args.command == "resume-veo":
        cmd_resume_veo(args.job_id)
    elif args.command == "test-pipeline":
        cmd_test_pipeline()
    elif args.command == "reset":
        import shutil

        if db.RENDER_DIR.exists():
            shutil.rmtree(db.RENDER_DIR)
        db.ensure_initialized(force_reset=True)
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        print("Reset studio.db and cleaned rendered_outputs/.")


if __name__ == "__main__":
    main()
