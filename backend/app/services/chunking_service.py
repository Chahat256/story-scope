from typing import List, Tuple, Dict
import re
import logging

logger = logging.getLogger(__name__)


def count_words(text: str) -> int:
    return len(text.split())


def chunk_pages(
    pages: List[Tuple[int, str]],
    chunk_size_words: int = 300,
    chunk_overlap_words: int = 60,
) -> List[Dict]:
    """
    Chunk novel pages into overlapping chunks for embedding and retrieval.

    Returns list of dicts with:
        - chunk_id: str
        - text: str
        - page_start: int
        - page_end: int
        - word_count: int
    """
    # First, combine all pages into a flat list of (page_num, sentence) pairs
    all_sentences = []

    for page_num, text in pages:
        # Split into sentences (rough)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for s in sentences:
            s = s.strip()
            if s:
                all_sentences.append((page_num, s))

    chunks = []
    chunk_id = 0
    i = 0

    while i < len(all_sentences):
        # Build a chunk
        chunk_words = 0
        chunk_sentences = []
        chunk_pages_set = set()
        j = i

        while j < len(all_sentences) and chunk_words < chunk_size_words:
            page_num, sentence = all_sentences[j]
            words = count_words(sentence)
            chunk_sentences.append(sentence)
            chunk_pages_set.add(page_num)
            chunk_words += words
            j += 1

        if chunk_sentences:
            chunk_text = ' '.join(chunk_sentences)
            page_list = sorted(chunk_pages_set)

            chunks.append({
                "chunk_id": f"chunk_{chunk_id:05d}",
                "text": chunk_text,
                "page_start": page_list[0] if page_list else 0,
                "page_end": page_list[-1] if page_list else 0,
                "word_count": chunk_words,
            })
            chunk_id += 1

        # Advance with overlap
        overlap_words = 0
        while i < j and overlap_words < chunk_overlap_words:
            _, sentence = all_sentences[i]
            overlap_words += count_words(sentence)
            i += 1

        # Ensure we always advance at least some
        if i >= j:
            i = j

    logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
    return chunks
