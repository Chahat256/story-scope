import uuid
import os
import json
import asyncio
import logging
from typing import Dict, List
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.models.schemas import UploadResponse, JobStatusResponse, JobStatus, AnalysisReport
from app.services.pdf_service import extract_text_from_pdf, validate_pdf, get_pdf_metadata
from app.services.chunking_service import chunk_pages
from app.services.embedding_service import index_chunks
from app.services.analysis_service import run_full_analysis

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory job store (MVP: replace with SQLite in production)
jobs: Dict = {}


async def process_novel(job_id: str, pdf_path: str) -> None:
    """Background task: extract, chunk, index, analyze."""
    try:
        # Update status: extracting
        jobs[job_id]["status"] = JobStatus.EXTRACTING
        jobs[job_id]["message"] = "Extracting text from PDF..."
        jobs[job_id]["progress"] = 10
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc)

        pages = extract_text_from_pdf(pdf_path)

        if not pages:
            raise ValueError("No text could be extracted from this PDF.")

        jobs[job_id]["status"] = JobStatus.CHUNKING
        jobs[job_id]["message"] = f"Processing {len(pages)} pages..."
        jobs[job_id]["progress"] = 25
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc)

        chunks = chunk_pages(pages, chunk_size_words=300, chunk_overlap_words=60)

        jobs[job_id]["status"] = JobStatus.INDEXING
        jobs[job_id]["message"] = f"Indexing {len(chunks)} text chunks..."
        jobs[job_id]["progress"] = 40
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc)

        index_chunks(job_id, chunks)

        jobs[job_id]["status"] = JobStatus.ANALYZING
        jobs[job_id]["message"] = "Running literary analysis (this may take 1-2 minutes)..."
        jobs[job_id]["progress"] = 60
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc)

        report = run_full_analysis(job_id, pages)

        # Store report
        report_path = Path(settings.upload_dir) / f"{job_id}_report.json"
        report_path.write_text(report.model_dump_json(indent=2))

        jobs[job_id]["status"] = JobStatus.COMPLETE
        jobs[job_id]["message"] = "Analysis complete!"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc)
        jobs[job_id]["report_path"] = str(report_path)

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["message"] = f"Analysis failed: {str(e)}"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc)


@router.post("/upload", response_model=UploadResponse)
async def upload_novel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Check file size
    content = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_file_size_mb}MB."
        )

    if len(content) < 1000:
        raise HTTPException(status_code=400, detail="File appears to be empty or too small.")

    # Save file
    job_id = str(uuid.uuid4())
    upload_path = Path(settings.upload_dir) / f"{job_id}.pdf"
    upload_path.write_bytes(content)

    # Validate PDF content
    is_valid, validation_message = validate_pdf(str(upload_path))
    if not is_valid:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=validation_message)

    # Initialize job record
    now = datetime.now(timezone.utc)
    jobs[job_id] = {
        "job_id": job_id,
        "filename": file.filename,
        "status": JobStatus.PENDING,
        "progress": 0,
        "message": "Upload received, queuing for processing...",
        "created_at": now,
        "updated_at": now,
        "pdf_path": str(upload_path),
        "report_path": None,
    }

    # Queue background processing
    background_tasks.add_task(process_novel, job_id, str(upload_path))

    return UploadResponse(
        job_id=job_id,
        filename=file.filename,
        status=JobStatus.PENDING,
        message="Novel uploaded successfully. Processing has begun.",
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        filename=job["filename"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


@router.get("/report/{job_id}", response_model=AnalysisReport)
async def get_report(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]

    if job["status"] != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=202,
            detail=f"Analysis not yet complete. Current status: {job['status']}"
        )

    report_path = job.get("report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=500, detail="Report file not found.")

    report_data = json.loads(Path(report_path).read_text())
    return AnalysisReport(**report_data)
