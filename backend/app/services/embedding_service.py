import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Any, Tuple
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded singletons
_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None
_cross_encoder: Optional[CrossEncoder] = None

# In-memory BM25 store: job_id -> {"bm25": BM25Okapi, "texts": List[str], "metadatas": List[Dict], "ids": List[str]}
_bm25_indexes: Dict[str, Dict[str, Any]] = {}


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


def get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        logger.info("Loading cross-encoder model...")
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


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
    """Embed and store chunks in ChromaDB and build a BM25 index for a given job."""
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

    # Add to ChromaDB in batches
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch_end = min(i + batch_size, len(texts))
        collection.add(
            ids=ids[i:batch_end],
            embeddings=embeddings[i:batch_end],
            documents=texts[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )

    # Build BM25 index over the same chunks
    tokenized = [text.lower().split() for text in texts]
    bm25 = BM25Okapi(tokenized)
    _bm25_indexes[job_id] = {
        "bm25": bm25,
        "texts": texts,
        "metadatas": metadatas,
        "ids": ids,
    }

    logger.info(f"Indexed {len(chunks)} chunks for job {job_id} (ChromaDB + BM25)")


def _reciprocal_rank_fusion(
    rankings: List[List[str]], k: int = 60
) -> Dict[str, float]:
    """Merge multiple ranked lists of doc IDs using Reciprocal Rank Fusion."""
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def retrieve_chunks(job_id: str, query: str, top_k: int = 8) -> List[Dict]:
    """Hybrid retrieval: BM25 + dense vector search, RRF fusion, cross-encoder reranking.

    Pipeline:
      1. Dense (ChromaDB cosine) top-20  ┐ run in parallel
      2. BM25 top-20                     ┘
      3. Reciprocal Rank Fusion → unified top-20
      4. Cross-encoder rerank → final top-5
    """
    CANDIDATE_SIZE = 20
    FINAL_SIZE = min(max(top_k, 1), 10)  # honour caller's top_k, cap at 10
    RRF_K = 60

    model = get_embedding_model()
    collection = get_or_create_collection(job_id)

    # ── Dense search ──────────────────────────────────────────────────────────
    def dense_search() -> Tuple[List[str], Dict[str, str], Dict[str, Dict]]:
        query_embedding = model.encode([query]).tolist()
        n = min(CANDIDATE_SIZE, collection.count())
        if n == 0:
            return [], {}, {}
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        ids_ = results["ids"][0] if results["ids"] else []
        docs_ = results["documents"][0] if results["documents"] else []
        metas_ = results["metadatas"][0] if results["metadatas"] else []
        id_to_doc = {i: d for i, d in zip(ids_, docs_)}
        id_to_meta = {i: m for i, m in zip(ids_, metas_)}
        return ids_, id_to_doc, id_to_meta

    # ── BM25 search ───────────────────────────────────────────────────────────
    def bm25_search() -> Tuple[List[str], Dict[str, str], Dict[str, Dict]]:
        if job_id not in _bm25_indexes:
            return [], {}, {}
        store = _bm25_indexes[job_id]
        bm25_obj: BM25Okapi = store["bm25"]
        all_texts: List[str] = store["texts"]
        all_metas: List[Dict] = store["metadatas"]
        all_ids: List[str] = store["ids"]

        tokenized_query = query.lower().split()
        scores = bm25_obj.get_scores(tokenized_query)
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:CANDIDATE_SIZE]

        ranked_ids = [all_ids[i] for i in top_indices]
        id_to_doc = {all_ids[i]: all_texts[i] for i in top_indices}
        id_to_meta = {all_ids[i]: all_metas[i] for i in top_indices}
        return ranked_ids, id_to_doc, id_to_meta

    # ── Run both searches in parallel ─────────────────────────────────────────
    with ThreadPoolExecutor(max_workers=2) as executor:
        dense_future = executor.submit(dense_search)
        bm25_future = executor.submit(bm25_search)
        dense_ids, dense_doc, dense_meta = dense_future.result()
        bm25_ids, bm25_doc, bm25_meta = bm25_future.result()

    # ── Merge lookups ─────────────────────────────────────────────────────────
    all_id_to_doc: Dict[str, str] = {**dense_doc, **bm25_doc}
    all_id_to_meta: Dict[str, Dict] = {**dense_meta, **bm25_meta}

    if not all_id_to_doc:
        return []

    # ── Reciprocal Rank Fusion → top-20 candidates ───────────────────────────
    rrf_scores = _reciprocal_rank_fusion([dense_ids, bm25_ids], k=RRF_K)
    top20_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:CANDIDATE_SIZE]
    # Filter to IDs whose text we actually have
    top20_ids = [id_ for id_ in top20_ids if id_ in all_id_to_doc]

    if not top20_ids:
        return []

    # ── Cross-encoder reranking → top-5 ──────────────────────────────────────
    cross_enc = get_cross_encoder()
    pairs = [(query, all_id_to_doc[id_]) for id_ in top20_ids]
    ce_scores = cross_enc.predict(pairs)
    ranked = sorted(zip(top20_ids, ce_scores), key=lambda x: x[1], reverse=True)[:FINAL_SIZE]

    # ── Build output ──────────────────────────────────────────────────────────
    chunks: List[Dict] = []
    for id_, score in ranked:
        meta = all_id_to_meta.get(id_, {})
        doc = all_id_to_doc.get(id_, "")
        page_start = meta.get("page_start", "?")
        page_end = meta.get("page_end", page_start)
        page_ref = (
            f"p.{page_start}" if page_start == page_end else f"pp.{page_start}-{page_end}"
        )
        chunks.append({
            "text": doc,
            "page_reference": page_ref,
            "relevance_score": float(score),
        })

    return chunks


def delete_collection(job_id: str) -> None:
    """Delete a job's ChromaDB collection and BM25 index."""
    client = get_chroma_client()
    collection_name = f"novel_{job_id}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    _bm25_indexes.pop(job_id, None)
