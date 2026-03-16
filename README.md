# StoryScope — Literary Analysis for Novels

StoryScope is a portfolio-quality GenAI web application that generates deep, evidence-grounded literary analysis of uploaded novel PDFs. Upload a novel and receive structured analysis of characters, relationships, themes, and narrative tropes — all backed by passages from the text.

---

## Features

- **PDF Upload**: Drag-and-drop or click-to-browse upload of digital text PDFs (up to 50MB)
- **Character Analysis**: Identifies 2–6 major characters with traits, goals, conflicts, and key relationships
- **Relationship Mapping**: Maps significant character relationships (friendship, rivalry, romance, family, mentorship, conflict, etc.) with supporting passages
- **Theme Detection**: Identifies recurring themes and motifs with textual evidence and prevalence ratings
- **Trope Detection**: Matches narrative patterns against a curated 25-entry trope library with confidence levels
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
│           ├── embedding_service.py  # SentenceTransformers + ChromaDB
│           ├── analysis_service.py   # Claude-powered literary analysis
│           └── chat_service.py       # RAG chat with Claude
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

- **In-memory job store**: The MVP uses a Python dict for job state. This is intentional for simplicity; replace with SQLite/Redis for production.
- **Background tasks**: FastAPI `BackgroundTasks` runs the processing pipeline asynchronously after upload.
- **RAG pipeline**: Text is chunked at ~300 words with 60-word overlap, embedded with `all-MiniLM-L6-v2`, stored in ChromaDB, and retrieved per-query for both analysis and chat.
- **Analysis model**: `claude-sonnet-4-6` for deep analysis; `claude-haiku-4-5-20251001` for chat (faster, cheaper).
- **JSON-structured outputs**: All LLM calls return structured JSON, parsed directly into Pydantic models.

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- An Anthropic API key

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
# Edit .env and add your ANTHROPIC_API_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

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
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Required |
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
2. Set up backend (see above), ensuring `ANTHROPIC_API_KEY` is set
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
- **Job state is in-memory** — restarting the server clears all jobs
- **No authentication** — not suitable for public deployment as-is

### API Cost Estimates
A typical 300-page novel analysis uses approximately:
- Overview analysis: ~2,000 tokens
- Character analysis: ~5,000 tokens
- Relationship analysis: ~4,000 tokens
- Theme analysis: ~4,000 tokens
- Trope analysis: ~4,000 tokens
- Total: ~20,000 tokens per full analysis

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

**Backend**: Python, FastAPI, PyMuPDF, SentenceTransformers, ChromaDB, Anthropic Claude

**Frontend**: Next.js 14, TypeScript, TailwindCSS, TanStack Query, Axios, Lucide Icons
