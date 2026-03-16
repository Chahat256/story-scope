# CLAUDE.md — StoryScope Internal Project Guide

This file provides guidance for AI assistants and human contributors working on the StoryScope codebase.

---

## Project Purpose and Boundaries

StoryScope is a **portfolio-quality literary analysis web app** for uploaded novel PDFs. It is:
- A demonstration of RAG (Retrieval-Augmented Generation) applied to long-form text
- A showcase of structured LLM outputs (JSON-mode analysis pipelines)
- A real working tool for readers and students of literature

It is **not**:
- A general-purpose PDF chatbot
- A plagiarism detector
- A book summarizer (summaries are a byproduct, not the goal)
- A production SaaS (no auth, no billing, in-memory state)

---

## Repository Structure

```
story_scope/
├── backend/          # FastAPI Python backend
│   ├── main.py       # App entrypoint
│   └── app/
│       ├── core/config.py          # All settings via pydantic-settings
│       ├── models/schemas.py       # All Pydantic request/response models
│       ├── api/uploads.py          # Upload, status, report endpoints
│       ├── api/chat.py             # Chat endpoint
│       └── services/
│           ├── pdf_service.py      # PyMuPDF extraction + validation
│           ├── chunking_service.py # Word-count-based overlapping chunker
│           ├── embedding_service.py # SentenceTransformers + ChromaDB
│           ├── analysis_service.py # Claude analysis pipeline
│           └── chat_service.py     # RAG chat with Claude
└── frontend/         # Next.js 14 App Router TypeScript frontend
    └── src/
        ├── app/page.tsx                       # Landing page with upload
        ├── app/analysis/[jobId]/page.tsx      # Analysis dashboard
        ├── components/upload/                 # Upload UX components
        ├── components/dashboard/              # Six tab components
        ├── components/ui/                     # Shared UI primitives
        ├── lib/api.ts                         # Axios API client
        ├── lib/utils.ts                       # cn(), color helpers
        └── types/analysis.ts                 # TypeScript types
```

---

## Coding Standards

### Backend (Python)
- Use **type hints everywhere**. Functions must have complete parameter and return type annotations.
- Use **Pydantic models** for all request/response validation. Do not use raw dicts in API handlers.
- Services are **pure functions or simple classes** — no global mutable state except the lazy-loaded `_model` and `_chroma_client` singletons.
- All LLM prompts must request **JSON-only responses**. Parse with `json.loads()`. Wrap in try/except.
- Log at appropriate levels: `logger.info()` for milestones, `logger.error()` for failures.
- Use `from __future__ import annotations` if adding complex forward references.

### Frontend (TypeScript/Next.js)
- All components are **typed** — no `any` unless absolutely unavoidable (e.g., axios error handling).
- Use `"use client"` directive only for components that require browser APIs or state.
- Prefer **composition over inheritance**. Build from `Badge`, `PassageCard`, `Card` primitives.
- **No hardcoded API URLs** in components. All API calls go through `src/lib/api.ts`.
- TailwindCSS only — no inline styles, no CSS modules, no other CSS frameworks.
- Use the `cn()` utility from `lib/utils.ts` for conditional class names.

---

## Architecture Principles

### RAG Pipeline
The retrieval pipeline follows this order: **extract → chunk → embed → index → retrieve → generate**.

1. `pdf_service.py`: PyMuPDF extracts text page-by-page. Pages are cleaned (whitespace, hyphenation artifacts, page numbers).
2. `chunking_service.py`: Pages are split into sentences, then assembled into ~300-word chunks with 60-word overlap. Chunks track page ranges.
3. `embedding_service.py`: `all-MiniLM-L6-v2` embeds chunks. ChromaDB stores them with cosine similarity.
4. `analysis_service.py`: `build_sample_context()` retrieves top-K chunks per query topic, formats them as numbered passages, and passes to Claude.
5. `chat_service.py`: Same retrieval pattern, but with conversation history and a grounding-focused system prompt.

### Analysis Pipeline Order
The five analyses run **sequentially** and some depend on previous results:
1. `analyze_overview()` — uses first 20 pages of raw text
2. `analyze_characters()` — independent RAG query
3. `analyze_relationships()` — receives character list from step 2
4. `analyze_themes()` — independent RAG query
5. `analyze_tropes()` — receives character list from step 2

Do **not** parallelize these without careful consideration — the relationship and trope analyses need the character list.

### Job State
The MVP uses an in-memory `dict` (`jobs` in `uploads.py`). This is a deliberate choice for simplicity. If you need persistence:
- Use SQLite with SQLAlchemy (already in requirements)
- Store job metadata in DB, report JSON on disk (already done for reports)
- The `jobs` dict interface is already compatible with this upgrade

---

## UX Principles

- **Literary aesthetic**: The design uses a parchment color scheme, serif fonts for headings, and an ink-toned palette. Do not introduce bright accent colors or generic tech aesthetics.
- **Evidence first**: Every analysis claim must show supporting passages. Do not display conclusions without evidence.
- **Expandable cards**: Content should default to compact view (name + summary) with expansion for full detail. This keeps the page scannable.
- **Progress transparency**: The processing status page must show which stage is active. Users should never wonder if the app is frozen.
- **Interpretive language**: UI copy and LLM prompts must frame analysis as interpretation, not fact. Use "the text suggests", "evidence indicates", "appears to be".

---

## LLM Prompt Guidelines

- All analysis prompts end with: `Return only valid JSON array.` or `Respond only with valid JSON.`
- Prompts specify the **exact JSON schema** with field names and types.
- Prompts for tropes use the **exact trope IDs** from `TROPE_LIBRARY`. Do not allow free-form trope names.
- Character analysis asks for 2–6 characters. Trope analysis asks for 3–8 tropes. Relationship analysis asks for 3–8 relationships. These bounds prevent both under-analysis and hallucination bloat.
- Confidence fields should use natural language tiers: `"high | moderate | low"` for characters/relationships, `"strongly supported | moderately supported | weakly supported"` for tropes.

---

## Analysis Constraints

These are **hard constraints** enforced in the prompt design:

1. Trope IDs must come from `TROPE_LIBRARY` in `analysis_service.py`. Do not accept arbitrary trope names.
2. Relationship types must be one of the `RelationshipType` enum values. Invalid types are coerced to `complex`.
3. Supporting passages should be short excerpts or paraphrases (< 400 chars stored). They are not full paragraphs.
4. The analysis does not attempt to identify whether a novel is copyrighted. That is the user's responsibility.

---

## What is Explicitly Out of Scope

Do **not** implement the following without explicit approval:

- User authentication or accounts
- Payment/billing integration
- Publicly accessible deployment (the app has no rate limiting)
- OCR for scanned PDFs (Tesseract integration adds significant complexity)
- Translation of non-English novels
- Spoiler warnings or content filters
- Comparison between multiple novels
- Any feature that requires storing user PII

---

## Guidance for Future Contributors

### Adding a new analysis type (e.g., "Symbolism")
1. Add a new Pydantic model in `models/schemas.py`
2. Add an `analyze_symbolism()` function in `analysis_service.py` following the same pattern as `analyze_themes()`
3. Add the field to `AnalysisReport`
4. Call it in `run_full_analysis()`
5. Add a TypeScript interface in `frontend/src/types/analysis.ts`
6. Create a `SymbolismTab.tsx` component following the pattern of `ThemesTab.tsx`
7. Register the tab in `frontend/src/app/analysis/[jobId]/page.tsx`

### Adding a new trope to the library
Add an entry to `TROPE_LIBRARY` in `analysis_service.py`:
```python
{"id": "snake_id", "name": "Human-Readable Name", "description": "One sentence description"}
```
No other changes are needed — the trope list is injected into the prompt dynamically.

### Changing the embedding model
Replace `"all-MiniLM-L6-v2"` in `embedding_service.py`. Note that changing the model invalidates all existing ChromaDB collections — delete `chroma_db/` directory after switching models.

### Debugging analysis failures
1. Check FastAPI logs (`uvicorn` stdout) for the `Job {job_id} failed:` error with stack trace
2. The most common failure mode is LLM returning invalid JSON — add print/log of `response.content[0].text` before parsing
3. ChromaDB errors often indicate a version mismatch — check `chromadb==0.5.15` is installed
4. If the embedding model fails to load, it's usually a network issue downloading from HuggingFace Hub on first run

### Running in production
- Replace the in-memory `jobs` dict with a database-backed store
- Add a reverse proxy (nginx) in front of uvicorn
- Set `allow_origins` in CORS middleware to your actual domain
- Add API rate limiting (e.g., `slowapi`)
- Store `ANTHROPIC_API_KEY` in a secrets manager, not a `.env` file
- Consider using a task queue (Celery + Redis) instead of `BackgroundTasks` for the processing pipeline
