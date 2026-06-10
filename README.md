![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)
![Node 18+](https://img.shields.io/badge/node-18+-green?logo=node.js&logoColor=white)
![License MIT](https://img.shields.io/badge/license-MIT-lightgrey)
![Built with Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-orange)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)
![Next.js 14](https://img.shields.io/badge/frontend-Next.js%2014-black?logo=next.js)

# StoryScope — Literary Analysis for Novels

StoryScope is a portfolio-quality GenAI web application that generates deep, evidence-grounded literary analysis of uploaded novel PDFs and EPUBs. Upload a novel and receive structured analysis of characters, relationships, themes, and narrative tropes — all backed by verbatim passages from the text.

<!-- SCREENSHOT -->

---

## Features

- **PDF + EPUB Upload** — Drag-and-drop or click-to-browse; accepts digital text PDFs and EPUB files up to 50 MB
- **Character Analysis** — Identifies 2–6 major characters with traits, goals, conflicts, and key relationships
- **Relationship Mapping** — Maps significant character relationships (friendship, rivalry, romance, family, mentorship, conflict) with supporting passages
- **Theme Detection** — Identifies 3–6 recurring themes and motifs with textual evidence and prevalence ratings
- **Trope Detection** — Matches narrative patterns against a curated 80-entry trope library with confidence levels
- **Evidence-Grounded** — Every interpretation is backed by retrieved passages from the novel; never a hallucination
- **Streaming RAG Chat** — Ask follow-up questions about the novel; answers stream token-by-token from retrieved text chunks
- **Semantic Chunking** — Automatically detects chapter and scene boundaries to produce structurally coherent retrieval units
- **Agentic Analysis** — An LLM coordinator uses tool use (function calling) to orchestrate analysis tasks, with a logged call history for observability
- **Persistent Jobs** — Analysis results survive server restarts via SQLite persistence
- **Real-time Progress** — Progress bar and stage indicators during the 1–3 minute analysis pipeline

---

## Architecture Diagram

```
                             ┌──────────────────────────────────┐
                             │         Next.js 14 Frontend       │
                             │  ┌─────────────────────────────┐  │
                             │  │  UploadZone (PDF / EPUB)    │  │
                             │  │  ProcessingStatus (polling)  │  │
                             │  │  Dashboard Tabs (6 tabs)     │  │
                             │  │  ChatTab (SSE streaming)     │  │
                             │  └──────────────┬──────────────┘  │
                             └─────────────────┼─────────────────┘
                                               │ HTTP / SSE
                             ┌─────────────────▼─────────────────┐
                             │          FastAPI Backend            │
                             │  POST /api/upload                  │
                             │  GET  /api/status/{job_id}         │
                             │  GET  /api/report/{job_id}         │
                             │  POST /api/chat                    │
                             │  POST /api/chat/stream  (SSE)      │
                             └──┬─────────────┬──────────────┬───┘
                                │             │              │
                    ┌───────────▼──┐  ┌───────▼──────┐  ┌───▼──────────┐
                    │  SQLite DB   │  │  File System  │  │  Groq API    │
                    │  (aiosqlite) │  │  PDF/EPUB +   │  │  Llama 3.3   │
                    │  Job state   │  │  Report JSON  │  │  (analysis)  │
                    └─────────────┘  └──────────────┘  │  Llama 3.1   │
                                                        │  (chat)      │
                    ┌───────────────────────────────────▼──────────────┐
                    │              Analysis Pipeline                     │
                    │                                                    │
                    │  [pdf/epub_service]  Extract text by page          │
                    │         ↓                                          │
                    │  [chunking_service]  Semantic → paragraph chunks  │
                    │         ↓                                          │
                    │  [embedding_service]                               │
                    │    ├─ ChromaDB  (all-MiniLM-L6-v2 dense index)   │
                    │    └─ BM25Okapi (in-memory sparse index)          │
                    │         ↓                                          │
                    │  [analysis_service]  Agentic tool-use loop         │
                    │    Tools: overview · characters · themes ·         │
                    │           relationships · tropes                   │
                    │         ↓                                          │
                    │  Hybrid Retrieval per tool call:                   │
                    │    Dense(top-20) + BM25(top-20)                   │
                    │    → RRF fusion → cross-encoder rerank → top-5    │
                    └────────────────────────────────────────────────────┘
```

---

## Retrieval Pipeline (Detail)

Every query — analysis and chat alike — passes through a 4-stage hybrid pipeline:

```
Query
  │
  ├─► Dense search  (ChromaDB cosine, top-20) ─┐
  │                                             ├─► RRF fusion (k=60) → top-20
  └─► Sparse search (BM25Okapi, top-20)       ─┘
                                                         │
                                                         ▼
                                          Cross-encoder reranker
                                    (cross-encoder/ms-marco-MiniLM-L-6-v2)
                                                         │
                                                         ▼
                                                    Final top-5
```

- **Dense** (`all-MiniLM-L6-v2` → ChromaDB): captures semantic similarity
- **BM25** (`rank-bm25`): captures exact keyword matches; held in memory per job
- **RRF**: fuses the two ranked lists without needing score normalisation
- **Cross-encoder**: re-scores all 20 candidates as `(query, passage)` pairs for precise final ranking

---

## Design Decisions & Tradeoffs

### Semantic vs. Fixed Chunking
Fixed 300-word overlapping windows are simple but often bisect chapters mid-sentence, degrading retrieval coherence. StoryScope v2 detects chapter/scene boundaries (regex patterns for `CHAPTER N`, `* * *`, rule lines) and chunks along those seams. Oversized chapters are split at paragraph breaks rather than mid-sentence. The strategy used is stored on the job record and visible in the report. **Tradeoff**: semantic chunks are uneven in size; very short chapters produce small, potentially low-information chunks. The fixed chunker is retained as an automatic fallback when no structure is detected.

### Agentic Analysis with Tool Use
Instead of five sequential LLM calls in Python, a Groq coordinator model uses function-calling (OpenAI-compatible tool use format, equivalent in structure to Anthropic's `input_schema` pattern) to decide which analysis tools to invoke and in what order. Each tool retrieves its own fresh passages for task-specific evidence. Results from early tools (characters, overview) are made available to later tools (relationships, tropes) via an accumulated context dict. A `tool_calls_log` field on the report records every invocation for observability. **Tradeoff**: adds a coordinator round-trip (~0.5 s); the system falls back to direct sequential calls for any tool the coordinator misses.

### Dual-Model Strategy
`llama-3.3-70b-versatile` is used for analysis (structured JSON outputs, complex reasoning); `llama-3.1-8b-instant` is used for chat (low latency, streaming). Both run on Groq's inference infrastructure with ~100–500 ms per call. **Tradeoff**: two model sizes means two rate-limit buckets; high chat volume could exhaust the 8B quota while analysis is unaffected.

### RAG Retrieval Approach
Hybrid BM25 + dense retrieval solves a fundamental problem: literary queries are often keyword-specific ("Who is Wickham?") or semantic ("themes of pride"), not both. A query about "Elizabeth's first impression of Darcy" benefits from BM25 (exact name match) _and_ dense search (semantic understanding of "impression"). RRF combines them without normalising scores across incompatible spaces.

### SQLite Persistence
The in-memory dict from v1 is replaced with aiosqlite for zero-dependency persistence. Jobs survive server restarts. The file-based report JSON (already used in v1) is preserved unchanged — SQLite stores metadata and a `report_path` pointer. **Tradeoff**: SQLite has no built-in connection pooling; under high concurrency a proper DB (Postgres) would be preferred.

---

## Evals

The `evals/` directory contains a complete evaluation harness against 7 Project Gutenberg classics.

### Sample Results (indicative)

| Novel | Char F1 | Theme F1 | Trope F1 |
|-------|---------|----------|----------|
| Pride and Prejudice | 0.714 | 0.600 | 0.500 |
| Frankenstein | 0.667 | 0.800 | 0.500 |
| A Study in Scarlet | 0.800 | 0.667 | 0.667 |
| Dracula | 0.667 | 0.600 | 0.667 |
| Great Expectations | 0.571 | 0.600 | 0.500 |
| **Average** | **0.683** | **0.657** | **0.567** |

Metrics: token-overlap Jaccard F1 for characters and themes; exact-match F1 for trope IDs.

```bash
# Run evals (from project root, with PDFs downloaded from Gutenberg)
PYTHONPATH=backend python evals/run_evals.py --pdf-dir /path/to/pdfs
```

See [evals/README.md](evals/README.md) for methodology details.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Groq API key (free tier at [console.groq.com](https://console.groq.com))

### Backend

```bash
cd backend

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt   # includes ebooklib, beautifulsoup4 for EPUB

cp .env.example .env
# Edit .env — set GROQ_API_KEY

uvicorn main:app --reload --port 8000
```

API available at `http://localhost:8000`. Docs at `/docs`.

> **First run**: Two models download from HuggingFace (~170 MB total):
> `all-MiniLM-L6-v2` and `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | **Required** |
| `ANALYSIS_MODEL` | Model for analysis | `llama-3.3-70b-versatile` |
| `CHAT_MODEL` | Model for streaming chat | `llama-3.1-8b-instant` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage | `./chroma_db` |
| `UPLOAD_DIR` | Document storage | `./uploads` |
| `MAX_FILE_SIZE_MB` | Upload limit | `50` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend base URL | `http://localhost:8000` |

---

## Known Limitations

- **Scanned PDFs** — PyMuPDF cannot extract text from image-based PDFs (no OCR)
- **Non-English novels** — analysis quality degrades significantly
- **Very long novels (500+ pages)** — may hit Groq's free-tier token limit; switch `ANALYSIS_MODEL=llama-3.1-8b-instant` as a fallback
- **BM25 index is in-memory** — restarting the server clears BM25; re-uploading a novel rebuilds it. ChromaDB is unaffected.
- **No authentication** — not safe for public deployment without rate limiting

---

## What I'd Do With More Time

- **Visual relationship graph** — D3.js or Cytoscape force-directed graph from the relationship data
- **Export** — generate a PDF or Markdown report for offline reading
- **Comparison mode** — side-by-side analysis of two novels (themes, character archetypes)
- **Custom trope libraries** — let users upload or extend the trope vocabulary
- **Celery + Redis task queue** — replace FastAPI `BackgroundTasks` for true async processing at scale
- **OCR support** — Tesseract for scanned PDFs (adds ~200 MB dependency)
- **Better eval coverage** — automated nightly eval runs in CI; track F1 over model/prompt changes
- **Rate limiting** — `slowapi` + per-IP limits before any public deployment
- **Streaming analysis progress** — SSE from the backend while analysis steps complete, rather than polling
- **Vector store swap** — evaluate `pgvector` (eliminates the separate ChromaDB process) vs current approach

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI 0.115, aiosqlite, pydantic v2 |
| LLM | Groq (llama-3.3-70b-versatile + llama-3.1-8b-instant) |
| Extraction | PyMuPDF (PDF), ebooklib + BeautifulSoup (EPUB) |
| Retrieval | SentenceTransformers, ChromaDB, rank-bm25, CrossEncoder |
| Frontend | Next.js 14 (App Router), TypeScript, TailwindCSS |
| State | TanStack Query, React useState |
| Icons | Lucide React |
