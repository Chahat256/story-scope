"""
Chat endpoints for StoryScope.

POST /api/chat         — original synchronous response (kept for backward compat)
POST /api/chat/stream  — Server-Sent Events streaming response

Both endpoints look up job state from SQLite (no longer imports from uploads.py).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import chat_with_novel, stream_chat_with_novel
from app.services.database import get_job

router = APIRouter()
logger = logging.getLogger(__name__)


async def _resolve_job_and_summary(job_id: str) -> tuple[dict, str]:
    """Shared validation and context-building for both chat endpoints."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail="Analysis must be complete before chatting.",
        )

    analysis_summary = ""
    report_path = job.get("report_path")
    if report_path and Path(report_path).exists():
        try:
            report_data = json.loads(Path(report_path).read_text())
            overview = report_data.get("overview", {})
            chars = report_data.get("characters", [])
            char_names = [c.get("name", "") for c in chars[:5]]
            analysis_summary = (
                f"Novel: {overview.get('title_guess', 'Unknown')}\n"
                f"Genre: {overview.get('genre_guess', '')}\n"
                f"Summary: {overview.get('narrative_summary', '')}\n"
                f"Main characters: {', '.join(char_names)}"
            )
        except Exception:
            pass

    return job, analysis_summary


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Synchronous chat endpoint (non-streaming). Kept for backward compatibility."""
    _, analysis_summary = await _resolve_job_and_summary(request.job_id)

    return chat_with_novel(
        job_id=request.job_id,
        message=request.message,
        history=request.history,
        analysis_summary=analysis_summary,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Streaming chat endpoint that emits SSE tokens as they arrive.

    Event format:
        data: {"type": "sources", "sources": [...]}     (first event)
        data: {"type": "token",   "token": "...", "done": false}
        data: {"type": "done",    "done": true}         (final event)
    """
    _, analysis_summary = await _resolve_job_and_summary(request.job_id)

    generator = stream_chat_with_novel(
        job_id=request.job_id,
        message=request.message,
        history=request.history,
        analysis_summary=analysis_summary,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # prevents nginx from buffering SSE
            "Connection": "keep-alive",
        },
    )
