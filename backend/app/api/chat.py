import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import chat_with_novel
from app.api.uploads import jobs

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    job_id = request.job_id

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]

    if job["status"] not in ["complete"]:
        raise HTTPException(
            status_code=400,
            detail="Analysis must be complete before chatting."
        )

    # Load analysis summary for context
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

    return chat_with_novel(
        job_id=job_id,
        message=request.message,
        history=request.history,
        analysis_summary=analysis_summary,
    )
