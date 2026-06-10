"""
Text chunking service for StoryScope.

Two strategies are available, selected automatically:

  "semantic"  — detects chapter/scene boundaries (CHAPTER headings, * * *,
                rule lines, etc.) and chunks along those natural seams.  If a
                chapter is too large it is split at paragraph breaks.
                Advantage: chunks don't bisect scenes mid-sentence, which
                improves retrieval coherence.  Disadvantage: chunk size is
                uneven; very short chapters become tiny chunks.

  "fixed"     — the original sentence-accumulating chunker that produces
                uniformly-sized overlapping windows.  Used as a fallback when
                no structural markers are found (e.g. single-chapter novellas,
                poorly formatted PDFs).

The selected strategy is returned alongside the chunks so callers can store
it for observability.
"""
from __future__ import annotations

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Boundary detection patterns ───────────────────────────────────────────────

_CHAPTER_PATTERNS = [
    # "Chapter 1", "Chapter I", "CHAPTER ONE", etc.
    re.compile(r"^\s*chapter\s+[\w\d]+", re.IGNORECASE | re.MULTILINE),
    # Part / Book headings
    re.compile(r"^\s*(part|book|volume|section)\s+[\w\d]+", re.IGNORECASE | re.MULTILINE),
    # Scene separators: * * *  or  ---  or  ~~~
    re.compile(r"^\s*(\*\s*){3,}\s*$", re.MULTILINE),
    re.compile(r"^\s*[-~=]{4,}\s*$", re.MULTILINE),
    # Roman-numeral-only line (e.g. "IV" as a chapter heading)
    re.compile(r"^\s*[IVXLCDM]{1,6}\s*$", re.MULTILINE),
]

# Minimum words a boundary-based section must have before it gets its own chunk.
# Sections smaller than this are merged with the next section.
_MIN_SECTION_WORDS = 50

# Maximum words per semantic chunk before we split at paragraph breaks.
_MAX_CHUNK_WORDS = 500

# Fixed-chunker defaults (used as fallback)
_FIXED_CHUNK_WORDS = 300
_FIXED_OVERLAP_WORDS = 60


def count_words(text: str) -> int:
    return len(text.split())


# ── Semantic chunking ─────────────────────────────────────────────────────────

def _detect_boundaries(pages: List[Tuple[int, str]]) -> bool:
    """Return True if enough structural markers exist for semantic chunking."""
    hits = 0
    for _, text in pages[:50]:  # sample first 50 pages
        for pat in _CHAPTER_PATTERNS:
            if pat.search(text):
                hits += 1
                break
    # Require at least 2 markers in the sample to trust semantic mode.
    return hits >= 2


def _split_page_into_sections(
    page_num: int, text: str
) -> List[Tuple[int, str]]:
    """Split a single page into sections at boundary markers.

    Returns list of (page_num, section_text) tuples.
    """
    # Build a combined splitter regex that captures the delimiter so we can
    # re-attach it to the section that starts with it.
    combined = re.compile(
        r"(?:^\s*(?:chapter|part|book|volume|section)\s+[\w\d]+.*$"
        r"|^\s*(\*\s*){3,}\s*$"
        r"|^\s*[-~=]{4,}\s*$"
        r"|^\s*[IVXLCDM]{1,6}\s*$)",
        re.MULTILINE | re.IGNORECASE,
    )

    parts = combined.split(text)
    if len(parts) <= 1:
        return [(page_num, text)]

    # Reconstruct sections: each split match becomes the opening of a new section.
    sections: List[Tuple[int, str]] = []
    current: List[str] = []
    for part in parts:
        if part is None:
            continue
        stripped = part.strip()
        if not stripped:
            continue
        # If this looks like a boundary marker line, start a new section.
        is_marker = any(p.fullmatch(stripped) for p in _CHAPTER_PATTERNS)
        if is_marker and current:
            combined_text = " ".join(current).strip()
            if combined_text:
                sections.append((page_num, combined_text))
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        combined_text = " ".join(current).strip()
        if combined_text:
            sections.append((page_num, combined_text))

    return sections or [(page_num, text)]


def _split_by_paragraphs(
    page_num: int, text: str, max_words: int
) -> List[Tuple[int, str]]:
    """Further split a long section at paragraph boundaries."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: List[Tuple[int, str]] = []
    current_parts: List[str] = []
    current_words = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        w = count_words(para)
        if current_words + w > max_words and current_parts:
            chunks.append((page_num, " ".join(current_parts)))
            current_parts = [para]
            current_words = w
        else:
            current_parts.append(para)
            current_words += w

    if current_parts:
        chunks.append((page_num, " ".join(current_parts)))

    return chunks or [(page_num, text)]


def _semantic_chunk(
    pages: List[Tuple[int, str]],
) -> List[Dict]:
    """Chunk by detected structure, splitting oversized sections at paragraphs."""
    # 1. Split each page into sections at boundary markers.
    raw_sections: List[Tuple[int, str]] = []
    for page_num, text in pages:
        raw_sections.extend(_split_page_into_sections(page_num, text))

    # 2. Merge tiny sections forward (avoids 10-word chapter-header chunks).
    merged: List[Tuple[int, str]] = []
    pending_text = ""
    pending_page = raw_sections[0][0] if raw_sections else 0
    for page_num, text in raw_sections:
        if count_words(pending_text + " " + text) < _MIN_SECTION_WORDS:
            pending_text = (pending_text + " " + text).strip()
        else:
            if pending_text:
                merged.append((pending_page, pending_text))
            pending_text = text
            pending_page = page_num
    if pending_text:
        merged.append((pending_page, pending_text))

    # 3. Split sections that exceed the max chunk size.
    final_sections: List[Tuple[int, str]] = []
    for page_num, text in merged:
        if count_words(text) > _MAX_CHUNK_WORDS:
            final_sections.extend(_split_by_paragraphs(page_num, text, _MAX_CHUNK_WORDS))
        else:
            final_sections.append((page_num, text))

    # 4. Format as chunk dicts.
    chunks: List[Dict] = []
    for idx, (page_num, text) in enumerate(final_sections):
        chunks.append(
            {
                "chunk_id": f"chunk_{idx:05d}",
                "text": text,
                "page_start": page_num,
                "page_end": page_num,
                "word_count": count_words(text),
            }
        )

    logger.info(f"Semantic chunking: {len(chunks)} chunks from {len(pages)} pages")
    return chunks


# ── Fixed (legacy) chunking ───────────────────────────────────────────────────

def _fixed_chunk(
    pages: List[Tuple[int, str]],
    chunk_size_words: int = _FIXED_CHUNK_WORDS,
    chunk_overlap_words: int = _FIXED_OVERLAP_WORDS,
) -> List[Dict]:
    """Original sentence-accumulating overlapping chunker."""
    all_sentences: List[Tuple[int, str]] = []
    for page_num, text in pages:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            s = s.strip()
            if s:
                all_sentences.append((page_num, s))

    chunks: List[Dict] = []
    chunk_id = 0
    i = 0

    while i < len(all_sentences):
        chunk_words = 0
        chunk_sentences: List[str] = []
        chunk_pages_set: set = set()
        j = i

        while j < len(all_sentences) and chunk_words < chunk_size_words:
            page_num, sentence = all_sentences[j]
            words = count_words(sentence)
            chunk_sentences.append(sentence)
            chunk_pages_set.add(page_num)
            chunk_words += words
            j += 1

        if chunk_sentences:
            chunk_text = " ".join(chunk_sentences)
            page_list = sorted(chunk_pages_set)
            chunks.append(
                {
                    "chunk_id": f"chunk_{chunk_id:05d}",
                    "text": chunk_text,
                    "page_start": page_list[0] if page_list else 0,
                    "page_end": page_list[-1] if page_list else 0,
                    "word_count": chunk_words,
                }
            )
            chunk_id += 1

        overlap_words = 0
        while i < j and overlap_words < chunk_overlap_words:
            _, sentence = all_sentences[i]
            overlap_words += count_words(sentence)
            i += 1

        if i >= j:
            i = j

    logger.info(f"Fixed chunking: {len(chunks)} chunks from {len(pages)} pages")
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_pages(
    pages: List[Tuple[int, str]],
    chunk_size_words: int = _FIXED_CHUNK_WORDS,
    chunk_overlap_words: int = _FIXED_OVERLAP_WORDS,
) -> Tuple[List[Dict], str]:
    """
    Chunk pages using semantic boundaries when available, fixed chunking otherwise.

    Returns:
        (chunks, strategy) where strategy is "semantic" or "fixed".
    """
    if _detect_boundaries(pages):
        logger.info("Structural markers detected — using semantic chunking")
        return _semantic_chunk(pages), "semantic"
    else:
        logger.info("No structural markers found — falling back to fixed chunking")
        return _fixed_chunk(pages, chunk_size_words, chunk_overlap_words), "fixed"
