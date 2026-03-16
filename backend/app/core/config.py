from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    groq_api_key: str
    database_url: str = "sqlite+aiosqlite:///./storyscope.db"
    chroma_persist_dir: str = "./chroma_db"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    # LLM settings
    analysis_model: str = "llama-3.3-70b-versatile"
    chat_model: str = "llama-3.1-8b-instant"

    # Chunking settings
    chunk_size: int = 800
    chunk_overlap: int = 150

    # Retrieval settings
    top_k_chunks: int = 8

    class Config:
        env_file = ".env"


settings = Settings()

# Ensure directories exist
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
