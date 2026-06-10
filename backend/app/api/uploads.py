"""
Upload, status, and report endpoints.

Job state is now persisted to SQLite via database.py instead of the in-memory
dict. This means jobs survive server restarts and can be retrieved by ID at any
time. The API contract (request/response shapes, URL paths) is unchanged.

EPUB support: .epub files are accepted alongside .pdf files. The upload endpoint
detects the file type and routes to the appropriate extraction service.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.models.schemas import AnalysisReport, JobStatus, JobStatusResponse, UploadResponse
from app.services.analysis_service import run_full_analysis
from app.services.chunking_service import chunk_pages
from app.services.database import create_job, get_job, update_job
from app.services.embedding_service import index_chunks
from app.services.pdf_service import extract_text_from_pdf, validate_pdf

router = APIRouter()
logger = logging.getLogger(__name__)

_ACCEPTED_EXTENSIONS = {".pdf", ".epub"}
_ACCEPTED_MIME = {
    "application/pdf",
    "application/epub+zip",
    "application/epub",
}


def _is_epub(filename: str) -> bool:
    return filename.lower().endswith(".epub")


async def process_novel(job_id: str, file_path: str) -> None:
    """Background task: extract → chunk → index → analyse → persist."""
    try:
        await update_job(job_id, status=JobStatus.EXTRACTING, message="Extracting text from document...", progress=10)

        is_epub = _is_epub(file_path)
        if is_epub:
            # Import lazily so the service is optional when ebooklib is absent
            from app.services.epub_service import extract_text_from_epub
            pages = extract_text_from_epub(file_path)
        else:
            pages = extract_text_from_pdf(file_path)

        if not pages:
            raise ValueError("No text could be extracted from this document.")

        await update_job(
            job_id,
            status=JobStatus.CHUNKING,
            message=f"Processing {len(pages)} pages...",
            progress=25,
        )

        # chunk_pages now returns (chunks, strategy)
        chunks, chunking_strategy = chunk_pages(pages, chunk_size_words=300, chunk_overlap_words=60)

        await update_job(
            job_id,
            status=JobStatus.INDEXING,
            message=f"Indexing {len(chunks)} text chunks ({chunking_strategy} chunking)...",
            progress=40,
            chunking_strategy=chunking_strategy,
        )

        index_chunks(job_id, chunks)

        await update_job(
            job_id,
            status=JobStatus.ANALYZING,
            message="Running literary analysis (this may take 1-2 minutes)...",
            progress=60,
        )

        report = run_full_analysis(job_id, pages)
        # Propagate chunking strategy into the report
        report = report.model_copy(update={"chunking_strategy": chunking_strategy})

        report_path = Path(settings.upload_dir) / f"{job_id}_report.json"
        report_path.write_text(report.model_dump_json(indent=2))

        await update_job(
            job_id,
            status=JobStatus.COMPLETE,
            message="Analysis complete!",
            progress=100,
            report_path=str(report_path),
        )
        logger.info(f"Job {job_id} completed — {len(chunks)} chunks, strategy={chunking_strategy}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        await update_job(
            job_id,
            status=JobStatus.FAILED,
            message=f"Analysis failed: {str(e)}",
            progress=0,
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_novel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    """Accept a PDF or EPUB novel, validate it, and queue analysis."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in _ACCEPTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and EPUB files are accepted.")

    content = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_file_size_mb}MB.",
        )
    if len(content) < 1000:
        raise HTTPException(status_code=400, detail="File appears to be empty or too small.")

    job_id = str(uuid.uuid4())
    upload_path = Path(settings.upload_dir) / f"{job_id}{ext}"
    upload_path.write_bytes(content)

    # Validate document content
    if ext == ".pdf":
        is_valid, validation_message = validate_pdf(str(upload_path))
    else:
        from app.services.epub_service import validate_epub
        is_valid, validation_message = validate_epub(str(upload_path))

    if not is_valid:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=validation_message)

    now = datetime.now(timezone.utc)
    await create_job(job_id, filename, str(upload_path), now)

    background_tasks.add_task(process_novel, job_id, str(upload_path))

    return UploadResponse(
        job_id=job_id,
        filename=filename,
        status=JobStatus.PENDING,
        message="Novel uploaded successfully. Processing has begun.",
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"] or "",
        filename=job["filename"],
        created_at=datetime.fromisoformat(job["created_at"]),
        updated_at=datetime.fromisoformat(job["updated_at"]),
    )


@router.get("/report/{job_id}", response_model=AnalysisReport)
async def get_report(job_id: str) -> AnalysisReport:
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job["status"] != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=202,
            detail=f"Analysis not yet complete. Current status: {job['status']}",
        )

    report_path = job.get("report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=500, detail="Report file not found.")

    report_data = json.loads(Path(report_path).read_text())
    return AnalysisReport(**report_data)
