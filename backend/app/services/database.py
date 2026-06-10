"""
Async SQLite persistence for StoryScope jobs.

Why: The in-memory dict in uploads.py is lost on every server restart, making it
impossible to revisit a completed analysis after a crash or redeploy. This module
provides a thin async wrapper over aiosqlite so jobs survive restarts while keeping
the single-file MVP architecture intact (no ORM, no migrations framework).
"""
from __future__ import annotations

import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Database file lives next to where the server is started (the backend/ dir).
DB_PATH = Path("storyscope.db")


async def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id           TEXT PRIMARY KEY,
                filename         TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'pending',
                progress         INTEGER NOT NULL DEFAULT 0,
                message          TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                pdf_path         TEXT,
                report_path      TEXT,
                chunking_strategy TEXT DEFAULT 'fixed'
            )
            """
        )
        await db.commit()


async def create_job(
    job_id: str,
    filename: str,
    pdf_path: str,
    now: datetime,
) -> None:
    """Insert a new job record with pending status."""
    ts = now.isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO jobs
              (job_id, filename, status, progress, message, created_at, updated_at, pdf_path)
            VALUES (?, ?, 'pending', 0, 'Upload received, queuing for processing...', ?, ?, ?)
            """,
            (job_id, filename, ts, ts, pdf_path),
        )
        await db.commit()


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return a job dict by ID, or None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def update_job(job_id: str, **fields: Any) -> None:
    """Update arbitrary job fields. Always refreshes updated_at.

    Example:
        await update_job(job_id, status="analyzing", progress=60)
    """
    if not fields:
        return
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = [*fields.values(), job_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values
        )
        await db.commit()


async def list_jobs() -> List[Dict[str, Any]]:
    """Return all jobs ordered by creation date, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
