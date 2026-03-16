import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy-load model
_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
        )
    return _chroma_client


def get_or_create_collection(job_id: str) -> chromadb.Collection:
    client = get_chroma_client()
    collection_name = f"novel_{job_id}"
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    return collection


def index_chunks(job_id: str, chunks: List[Dict]) -> None:
    """Embed and store chunks in ChromaDB for a given job."""
    model = get_embedding_model()
    collection = get_or_create_collection(job_id)

    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [
        {
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "word_count": c["word_count"],
        }
        for c in chunks
    ]

    logger.info(f"Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    # Add in batches to avoid memory issues
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch_end = min(i + batch_size, len(texts))
        collection.add(
            ids=ids[i:batch_end],
            embeddings=embeddings[i:batch_end],
            documents=texts[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )

    logger.info(f"Indexed {len(chunks)} chunks for job {job_id}")


def retrieve_chunks(job_id: str, query: str, top_k: int = 8) -> List[Dict]:
    """Retrieve top-k relevant chunks for a query."""
    model = get_embedding_model()
    collection = get_or_create_collection(job_id)

    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            page_ref = f"p.{meta['page_start']}"
            if meta['page_end'] != meta['page_start']:
                page_ref = f"pp.{meta['page_start']}-{meta['page_end']}"

            chunks.append({
                "text": doc,
                "page_reference": page_ref,
                "relevance_score": 1 - dist,  # cosine similarity
            })

    return chunks


def delete_collection(job_id: str) -> None:
    """Delete a job's collection from ChromaDB."""
    client = get_chroma_client()
    collection_name = f"novel_{job_id}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
