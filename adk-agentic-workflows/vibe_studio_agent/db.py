"""SQLite persistence layer for VibeStudio Agentic Workflow (RAG, Memory Bank, HITL, Async Veo).

Automatically creates and seeds `vibe_studio_agent/data/studio.db` from:
  - `data/brand_guidelines.md`
  - `data/production_playbook.md`
  - `data/audience_insights.md`
  - `data/creator_memories.json`
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "studio.db"
RENDER_DIR = Path(__file__).resolve().parent / "rendered_outputs"

SCENE_COST_USD = 3.50
MAX_BUDGET_USD = 15.00
TARGET_SCENE_COUNT = 3
SCENE_DURATION_SEC = 8

BANNED_TROPES = [
    "flashing strobe",
    "rapid flickering lights",
    "guaranteed profit",
    "get rich quick",
    "gore",
    "explicit violence",
    "unlicensed celebrity likeness",
    "copyrighted logo",
    "clickbait shock face",
]

KNOWLEDGE_FILES = [
    ("DOC-BRAND-01", "brand_guidelines.md", "Brand & Safety Guidelines"),
    ("DOC-PLAYBOOK-02", "production_playbook.md", "24-Second Production Playbook"),
    ("DOC-INSIGHTS-03", "audience_insights.md", "Audience Retention & Engagement Insights"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_initialized(force_reset: bool = False) -> None:
    """Create tables and seed the Enterprise RAG corpus and Memory Bank if empty."""
    if force_reset and DB_PATH.exists():
        DB_PATH.unlink()

    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                doc_title TEXT NOT NULL,
                section_heading TEXT NOT NULL,
                content TEXT NOT NULL,
                source_file TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS creator_memories (
                memory_id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                category TEXT NOT NULL,
                preference TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS storyboards (
                storyboard_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                aspect_ratio TEXT NOT NULL,
                scenes_json TEXT NOT NULL,
                total_duration_sec INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                policy_status TEXT NOT NULL,
                policy_Violations_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hitl_tickets (
                ticket_id TEXT PRIMARY KEY,
                storyboard_id TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer_notes TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS veo_jobs (
                job_id TEXT PRIMARY KEY,
                storyboard_id TEXT NOT NULL,
                ticket_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                operation_name TEXT NOT NULL,
                keyframes_json TEXT NOT NULL,
                scene_videos_json TEXT NOT NULL,
                final_video_uri TEXT,
                poll_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            """
        )

        # Seed knowledge chunks from Markdown files if empty
        count = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
        if count == 0:
            _seed_knowledge_chunks(conn)

        # Seed creator memories from JSON if empty
        mem_count = conn.execute("SELECT COUNT(*) FROM creator_memories").fetchone()[0]
        if mem_count == 0:
            _seed_creator_memories(conn)


def _seed_knowledge_chunks(conn: sqlite3.Connection) -> None:
    chunk_idx = 1
    for doc_id, filename, doc_title in KNOWLEDGE_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        raw_text = path.read_text(encoding="utf-8")
        sections = re.split(r"\n(?=##\s+)", raw_text)
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            first_line = sec.splitlines()[0].lstrip("# ").strip()
            chunk_id = f"CHUNK-{chunk_idx:03d}"
            chunk_idx += 1
            conn.execute(
                """
                INSERT INTO knowledge_chunks (
                    chunk_id, doc_id, doc_title, section_heading, content, source_file
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, doc_id, doc_title, first_line, sec, filename),
            )


def _seed_creator_memories(conn: sqlite3.Connection) -> None:
    mem_file = DATA_DIR / "creator_memories.json"
    if not mem_file.exists():
        return
    records = json.loads(mem_file.read_text(encoding="utf-8"))
    now = _utc_now()
    for item in records:
        conn.execute(
            """
            INSERT INTO creator_memories (
                memory_id, creator_id, category, preference, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item["memory_id"],
                item.get("creator_id", "creator-default"),
                item["category"],
                item["preference"],
                item.get("source", "seed_memory_bank"),
                now,
            ),
        )


# ---------------------------------------------------------------------------
# Enterprise Knowledge Base (RAG) Queries
# ---------------------------------------------------------------------------
def search_knowledge_chunks(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    """Search indexed enterprise knowledge chunks by keyword relevance."""
    ensure_initialized()
    tokens = [
        t.lower()
        for t in re.findall(r"[a-zA-Z0-9_]+", query)
        if len(t) > 2
    ]
    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM knowledge_chunks").fetchall()]

    if not tokens:
        return rows[:top_k]

    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        haystack = f"{row['doc_title']} {row['section_heading']} {row['content']}".lower()
        score = sum(3 if t in row["section_heading"].lower() else 1 for t in tokens if t in haystack)
        scored.append((score, row))

    scored.sort(key=lambda item: (item[0], item[1]["chunk_id"]), reverse=True)
    results = [item[1] for item in scored if item[0] > 0]
    return (results or rows)[:top_k]


# ---------------------------------------------------------------------------
# Persistent Memory Bank Operations
# ---------------------------------------------------------------------------
def list_creator_memories(creator_id: str = "creator-default") -> list[dict[str, Any]]:
    ensure_initialized()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM creator_memories WHERE creator_id = ? ORDER BY memory_id ASC",
            (creator_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_creator_memory(
    category: str,
    preference: str,
    creator_id: str = "creator-default",
    source: str = "agent_callback",
) -> dict[str, Any]:
    ensure_initialized()
    now = _utc_now()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT memory_id FROM creator_memories WHERE creator_id = ? AND category = ?",
            (creator_id, category),
        ).fetchone()
        if existing:
            memory_id = existing["memory_id"]
            conn.execute(
                """
                UPDATE creator_memories
                SET preference = ?, source = ?, updated_at = ?
                WHERE memory_id = ?
                """,
                (preference, source, now, memory_id),
            )
        else:
            count = conn.execute("SELECT COUNT(*) FROM creator_memories").fetchone()[0]
            memory_id = f"MEM-{101 + count}"
            conn.execute(
                """
                INSERT INTO creator_memories (
                    memory_id, creator_id, category, preference, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (memory_id, creator_id, category, preference, source, now),
            )
    return {
        "memory_id": memory_id,
        "creator_id": creator_id,
        "category": category,
        "preference": preference,
        "source": source,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# Storyboard & Policy Evaluation Persistence
# ---------------------------------------------------------------------------
def evaluate_storyboard_compliance(
    scenes: list[dict[str, Any]],
    aspect_ratio: str = "16:9",
) -> dict[str, Any]:
    """Deterministically check a storyboard against VibeStudio enterprise brand rules."""
    violations: list[str] = []

    if len(scenes) != TARGET_SCENE_COUNT:
        violations.append(
            f"Scene count violation: expected exactly {TARGET_SCENE_COUNT} scenes (24s total), got {len(scenes)}."
        )

    total_duration = sum(int(s.get("duration_sec", SCENE_DURATION_SEC)) for s in scenes)
    if total_duration > TARGET_SCENE_COUNT * SCENE_DURATION_SEC:
        violations.append(
            f"Duration violation: total duration {total_duration}s exceeds 24s playbook limit."
        )

    estimated_cost = round(len(scenes) * SCENE_COST_USD, 2)
    if estimated_cost > MAX_BUDGET_USD:
        violations.append(
            f"Budget violation: estimated cost ${estimated_cost:.2f} exceeds ${MAX_BUDGET_USD:.2f} cap."
        )

    for idx, scene in enumerate(scenes, start=1):
        combined_text = (
            f"{scene.get('visual_prompt', '')} {scene.get('voiceover', '')} {scene.get('camera_motion', '')}"
        ).lower()
        for trope in BANNED_TROPES:
            if trope in combined_text:
                violations.append(
                    f"Banned trope '{trope}' detected in Scene {idx} (violates DOC-BRAND-01)."
                )
        if not scene.get("camera_motion"):
            violations.append(f"Scene {idx} is missing explicit camera_motion specification.")

    status = "COMPLIANT" if not violations else "VIOLATION"
    return {
        "policy_status": status,
        "scene_count": len(scenes),
        "total_duration_sec": total_duration,
        "estimated_cost_usd": estimated_cost,
        "aspect_ratio": aspect_ratio,
        "violations": violations,
    }


def save_storyboard(
    topic: str,
    scenes: list[dict[str, Any]],
    aspect_ratio: str = "16:9",
    storyboard_id: Optional[str] = None,
) -> dict[str, Any]:
    ensure_initialized()
    audit = evaluate_storyboard_compliance(scenes=scenes, aspect_ratio=aspect_ratio)
    now = _utc_now()

    with get_connection() as conn:
        if not storyboard_id:
            count = conn.execute("SELECT COUNT(*) FROM storyboards").fetchone()[0]
            storyboard_id = f"SB-{1001 + count}"

        conn.execute(
            """
            INSERT OR REPLACE INTO storyboards (
                storyboard_id, topic, aspect_ratio, scenes_json,
                total_duration_sec, estimated_cost_usd, policy_status,
                policy_Violations_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                storyboard_id,
                topic,
                aspect_ratio,
                json.dumps(scenes),
                audit["total_duration_sec"],
                audit["estimated_cost_usd"],
                audit["policy_status"],
                json.dumps(audit["violations"]),
                now,
            ),
        )

    return {
        "storyboard_id": storyboard_id,
        "topic": topic,
        "aspect_ratio": aspect_ratio,
        "scenes": scenes,
        "total_duration_sec": audit["total_duration_sec"],
        "estimated_cost_usd": audit["estimated_cost_usd"],
        "policy_status": audit["policy_status"],
        "violations": audit["violations"],
        "created_at": now,
    }


def fetch_storyboard(storyboard_id: str) -> Optional[dict[str, Any]]:
    ensure_initialized()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM storyboards WHERE storyboard_id = ?",
            (storyboard_id.strip().upper(),),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["scenes"] = json.loads(data.pop("scenes_json"))
        data["violations"] = json.loads(data.pop("policy_Violations_json"))
        return data


# ---------------------------------------------------------------------------
# Human-in-the-Loop (HITL) Approval Tickets
# ---------------------------------------------------------------------------
def create_hitl_ticket(storyboard_id: str, notes: str = "") -> dict[str, Any]:
    ensure_initialized()
    now = _utc_now()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM hitl_tickets WHERE storyboard_id = ? ORDER BY created_at DESC LIMIT 1",
            (storyboard_id,),
        ).fetchone()
        if existing and existing["status"] == "PENDING_APPROVAL":
            return dict(existing)

        count = conn.execute("SELECT COUNT(*) FROM hitl_tickets").fetchone()[0]
        ticket_id = f"HITL-{2001 + count}"
        conn.execute(
            """
            INSERT INTO hitl_tickets (
                ticket_id, storyboard_id, status, reviewer_notes, created_at, resolved_at
            ) VALUES (?, ?, 'PENDING_APPROVAL', ?, ?, NULL)
            """,
            (ticket_id, storyboard_id, notes, now),
        )
    return {
        "ticket_id": ticket_id,
        "storyboard_id": storyboard_id,
        "status": "PENDING_APPROVAL",
        "reviewer_notes": notes,
        "created_at": now,
        "resolved_at": None,
    }


def update_hitl_ticket(
    ticket_id: str,
    decision: str,
    reviewer_notes: str = "",
) -> Optional[dict[str, Any]]:
    """Decision must be 'APPROVED' or 'REVISION_REQUESTED'."""
    ensure_initialized()
    normalized = decision.strip().upper()
    if normalized not in ("APPROVED", "REVISION_REQUESTED"):
        raise ValueError("decision must be 'APPROVED' or 'REVISION_REQUESTED'")
    now = _utc_now()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_tickets WHERE ticket_id = ?",
            (ticket_id.strip().upper(),),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE hitl_tickets
            SET status = ?, reviewer_notes = ?, resolved_at = ?
            WHERE ticket_id = ?
            """,
            (normalized, reviewer_notes, now, ticket_id.strip().upper()),
        )
        updated = conn.execute(
            "SELECT * FROM hitl_tickets WHERE ticket_id = ?",
            (ticket_id.strip().upper(),),
        ).fetchone()
        return dict(updated)


def fetch_hitl_ticket(ticket_id: str) -> Optional[dict[str, Any]]:
    ensure_initialized()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_tickets WHERE ticket_id = ?",
            (ticket_id.strip().upper(),),
        ).fetchone()
        return dict(row) if row else None


def fetch_latest_hitl_for_storyboard(storyboard_id: str) -> Optional[dict[str, Any]]:
    ensure_initialized()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_tickets WHERE storyboard_id = ? ORDER BY created_at DESC LIMIT 1",
            (storyboard_id.strip().upper(),),
        ).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Asynchronous Veo Video Jobs
# ---------------------------------------------------------------------------
def create_veo_job(
    storyboard_id: str,
    ticket_id: str,
    mode: str,
    operation_name: str,
    keyframes: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_initialized()
    now = _utc_now()
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM veo_jobs").fetchone()[0]
        job_id = f"VEO-{3001 + count}"
        conn.execute(
            """
            INSERT INTO veo_jobs (
                job_id, storyboard_id, ticket_id, mode, status,
                operation_name, keyframes_json, scene_videos_json,
                final_video_uri, poll_count, created_at, completed_at
            ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, '[]', NULL, 0, ?, NULL)
            """,
            (
                job_id,
                storyboard_id,
                ticket_id,
                mode,
                operation_name,
                json.dumps(keyframes),
                now,
            ),
        )
    return fetch_veo_job(job_id)  # type: ignore[return-value]


def fetch_veo_job(job_id: str) -> Optional[dict[str, Any]]:
    ensure_initialized()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM veo_jobs WHERE job_id = ?",
            (job_id.strip().upper(),),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["keyframes"] = json.loads(data.pop("keyframes_json"))
        data["scene_videos"] = json.loads(data.pop("scene_videos_json"))
        return data


def complete_veo_job(
    job_id: str,
    scene_videos: list[dict[str, Any]],
    final_video_uri: str,
) -> Optional[dict[str, Any]]:
    ensure_initialized()
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE veo_jobs
            SET status = 'COMPLETED',
                scene_videos_json = ?,
                final_video_uri = ?,
                poll_count = poll_count + 1,
                completed_at = ?
            WHERE job_id = ?
            """,
            (json.dumps(scene_videos), final_video_uri, now, job_id.strip().upper()),
        )
    return fetch_veo_job(job_id)


def list_all_studio_records() -> dict[str, Any]:
    ensure_initialized()
    with get_connection() as conn:
        memories = [dict(r) for r in conn.execute("SELECT * FROM creator_memories").fetchall()]
        storyboards = [dict(r) for r in conn.execute("SELECT * FROM storyboards").fetchall()]
        tickets = [dict(r) for r in conn.execute("SELECT * FROM hitl_tickets").fetchall()]
        jobs = [dict(r) for r in conn.execute("SELECT * FROM veo_jobs").fetchall()]
        chunks = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
    return {
        "knowledge_chunk_count": chunks,
        "creator_memories": memories,
        "storyboards": storyboards,
        "hitl_tickets": tickets,
        "veo_jobs": jobs,
    }
