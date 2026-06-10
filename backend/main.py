from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.uploads import router as uploads_router
from app.api.chat import router as chat_router
from app.services.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize persistent storage on startup."""
    logger.info("Initializing SQLite database...")
    await init_db()
    logger.info("Database ready.")
    yield
    # Nothing to clean up on shutdown for this MVP


app = FastAPI(
    title="StoryScope API",
    description="Literary analysis API for uploaded novel PDFs and EPUBs",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads_router, prefix="/api", tags=["uploads"])
app.include_router(chat_router, prefix="/api", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "StoryScope API", "version": "2.0.0"}
