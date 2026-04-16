# StoryScope — Literary Analysis for Novels

StoryScope is a portfolio-quality GenAI web application that generates deep, evidence-grounded literary analysis of uploaded novel PDFs. Upload a novel and receive structured analysis of characters, relationships, themes, and narrative tropes — all backed by passages from the text.

---

## Features

- **PDF Upload**: Drag-and-drop or click-to-browse upload of digital text PDFs (up to 50MB)
- **Character Analysis**: Identifies 2–6 major characters with traits, goals, conflicts, and key relationships
- **Relationship Mapping**: Maps significant character relationships (friendship, rivalry, romance, family, mentorship, conflict, etc.) with supporting passages
- **Theme Detection**: Identifies recurring themes and motifs with textual evidence and prevalence ratings
- **Trope Detection**: Matches narrative patterns against a curated 208-entry trope library with confidence levels
- **Evidence-Grounded**: Every interpretation is backed by retrieved passages from the novel
- **RAG Chat**: Ask follow-up questions about the novel; answers are grounded in retrieved text chunks
- **Real-time Processing Status**: Progress bar and stage indicators during analysis (1–3 minutes typical)

---

## Architecture Overview

```
StoryScope
├── backend/          # Python FastAPI REST API
│   ├── main.py       # App entrypoint, CORS, router registration
│   └── app/
│       ├── core/     # Configuration (pydantic-settings)
│       ├── models/   # Pydantic schemas (request/response models)
│       ├── api/      # Route handlers (uploads, chat)
│       └── services/ # Business logic
│           ├── pdf_service.py        # PyMuPDF text extraction
│           ├── chunking_service.py   # Sentence-aware overlapping chunking
│           ├── embedding_service.py  # Hybrid retrieval (BM25 + ChromaDB + cross-encoder)
│           ├── analysis_service.py   # Groq-powered literary analysis
│           └── chat_service.py       # RAG chat with Groq
└── frontend/         # Next.js 14 (App Router) TypeScript
    └── src/
        ├── app/      # Next.js pages (landing, analysis dashboard)
        ├── components/
        │   ├── upload/    # UploadZone, ProcessingStatus
        │   ├── dashboard/ # Six tab components
        │   └── ui/        # Badge, Card, PassageCard
        ├── lib/      # API client (axios), utility functions
        └── types/    # TypeScript interfaces matching backend schemas
```

### Key Design Decisions

- **In-memory job store**: The MVP uses a Python dict for job state. Intentional for simplicity; replace with SQLite/Redis for production.
- **Background tasks**: FastAPI `BackgroundTasks` runs the processing pipeline asynchronously after upload.
- **Hybrid RAG pipeline**: Text is chunked at ~300 words with 60-word overlap, then indexed in both ChromaDB (dense) and BM25 (sparse). At query time both indexes are searched in parallel, merged via Reciprocal Rank Fusion, and reranked with a cross-encoder. See [Retrieval Pipeline](#retrieval-pipeline) below.
- **LLM provider**: Groq (`llama-3.3-70b-versatile` for analysis, `llama-3.1-8b-instant` for chat).
- **JSON-structured outputs**: All LLM calls return structured JSON, parsed directly into Pydantic models.

---

## Retrieval Pipeline

Every query (both analysis and chat) goes through a 4-stage hybrid retrieval pipeline:

```
Query
  │
  ├─► Dense search (ChromaDB cosine, top-20)  ─┐
  │                                             ├─► Reciprocal Rank Fusion (k=60) → top-20
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
- **BM25** (`rank-bm25`): captures exact keyword matches; stored in-memory alongside the job
- **RRF**: fuses the two ranked lists without requiring score normalization
- **Cross-encoder**: re-scores all 20 candidates as `(query, passage)` pairs for precise relevance ranking

Both indexes are built at indexing time from the same chunks. The BM25 index lives in an in-memory dict (`_bm25_indexes`) keyed by `job_id`; the dense index lives in the persisted ChromaDB collection.

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Groq API key (free tier available at [console.groq.com](https://console.groq.com))

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

> **First run note**: On the first query after startup, two models will be downloaded from HuggingFace:
> - `all-MiniLM-L6-v2` (~90 MB) — embedding model
> - `cross-encoder/ms-marco-MiniLM-L-6-v2` (~80 MB) — reranker

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# .env.local already points to http://localhost:8000 by default

# Start the dev server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Your Groq API key | Required |
| `ANALYSIS_MODEL` | Groq model for analysis | `llama-3.3-70b-versatile` |
| `CHAT_MODEL` | Groq model for chat | `llama-3.1-8b-instant` |
| `DATABASE_URL` | SQLite connection string | `sqlite+aiosqlite:///./storyscope.db` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage directory | `./chroma_db` |
| `UPLOAD_DIR` | PDF upload storage directory | `./uploads` |
| `MAX_FILE_SIZE_MB` | Maximum upload size | `50` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8000` |

---

## How to Run Locally

1. Clone the repository
2. Set up backend (see above), ensuring `GROQ_API_KEY` is set
3. Set up frontend (see above)
4. Open `http://localhost:3000`
5. Upload a digital text novel PDF (not a scanned image)
6. Wait 1–3 minutes for analysis to complete
7. Explore the tabbed dashboard, then use the chat tab for follow-up questions

---

## Implementation Notes

### What Works Well
- Digital text PDFs (novels distributed as ebooks, Project Gutenberg downloads, etc.)
- English-language literary fiction, genre fiction, and classics
- Novels with clear character names and narrative structure

### Known Limitations
- **Scanned PDFs** (images of pages) are not supported — PyMuPDF cannot extract text from image-based PDFs
- **Very long novels** (500+ pages) may take 3+ minutes and consume significant API tokens
- **Non-English novels** may produce lower quality analysis
- **BM25 index is in-memory** — restarting the server clears BM25 indexes (ChromaDB persists to disk; re-uploading rebuilds BM25)
- **Job state is in-memory** — restarting the server clears all job metadata
- **No authentication** — not suitable for public deployment as-is
- **Groq free tier** has a 100K tokens/day limit on `llama-3.3-70b-versatile`; switch to `llama-3.1-8b-instant` via `ANALYSIS_MODEL` env var if you hit it

### API Cost Estimates
A typical 300-page novel analysis uses approximately:
- Overview analysis: ~2,000 tokens
- Character analysis: ~5,000 tokens
- Relationship analysis: ~4,000 tokens
- Theme analysis: ~4,000 tokens
- Trope analysis: ~6,000 tokens (larger trope library)
- Total: ~21,000 tokens per full analysis

---

## Future Improvements

- [ ] Persistent job storage with SQLite/PostgreSQL
- [ ] User authentication and job history
- [ ] Export analysis as PDF or Markdown
- [ ] Visual relationship graph (D3.js force-directed)
- [ ] Support for EPUB format
- [ ] Batch processing of multiple novels
- [ ] Comparison mode (analyze two novels side by side)
- [ ] Custom trope libraries
- [ ] Streaming responses for chat
- [ ] Better scanned PDF handling via OCR (Tesseract)
- [ ] Rate limiting and usage quotas

---

## Tech Stack

**Backend**: Python, FastAPI, PyMuPDF, SentenceTransformers, ChromaDB, BM25 (`rank-bm25`), Groq

**Frontend**: Next.js 14, TypeScript, TailwindCSS, TanStack Query, Axios, Lucide Icons
