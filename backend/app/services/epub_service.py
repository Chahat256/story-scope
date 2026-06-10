"""
EPUB text extraction service — sibling to pdf_service.py.

Uses ebooklib to parse EPUB containers and BeautifulSoup to strip HTML tags,
producing the same (page_number, text) tuple format that the rest of the pipeline
expects. 'Pages' for EPUBs are mapped to spine items (chapters) rather than
physical PDF pages.
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import List, Tuple

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# HTML tags whose inner text we discard entirely (nav, scripts, etc.)
_SKIP_TAGS = {"script", "style", "nav", "head"}


def _html_to_text(html_content: str) -> str:
    """Strip HTML and return clean plain text."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove boilerplate tags
    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse runs of spaces/tabs
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_text_from_epub(epub_path: str) -> List[Tuple[int, str]]:
    """
    Extract text from an EPUB file, returning (chapter_index, text) tuples.

    Each spine item (chapter/document) becomes one 'page'. Chapter index is
    1-based so it matches the convention used by pdf_service.
    """
    pages: List[Tuple[int, str]] = []

    try:
        book = epub.read_epub(epub_path, options={"ignore_ncx": True})
        chapter_num = 0

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            chapter_num += 1
            raw_html = item.get_content().decode("utf-8", errors="replace")
            text = _html_to_text(raw_html)

            if text:  # skip empty spine items (title pages with only images, etc.)
                pages.append((chapter_num, text))

        logger.info(f"Extracted {len(pages)} chapters from {epub_path}")
        return pages

    except Exception as e:
        logger.error(f"Failed to extract EPUB {epub_path}: {e}")
        raise


def validate_epub(epub_path: str) -> Tuple[bool, str]:
    """Validate that the file is a readable EPUB with extractable text."""
    try:
        book = epub.read_epub(epub_path, options={"ignore_ncx": True})
        items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        if not items:
            return False, "EPUB contains no readable spine items."

        # Check at least one item has text
        for item in items[:5]:
            html = item.get_content().decode("utf-8", errors="replace")
            if _html_to_text(html):
                return True, "Valid"

        return False, "EPUB does not appear to contain extractable text."

    except Exception as e:
        return False, f"Could not read EPUB: {str(e)}"


def get_epub_metadata(epub_path: str) -> dict:
    """Extract title, author, and item count from EPUB metadata."""
    try:
        book = epub.read_epub(epub_path, options={"ignore_ncx": True})
        title_meta = book.get_metadata("DC", "title")
        creator_meta = book.get_metadata("DC", "creator")
        items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

        return {
            "title": title_meta[0][0] if title_meta else "",
            "author": creator_meta[0][0] if creator_meta else "",
            "page_count": len(items),
            "format": "EPUB",
        }
    except Exception as e:
        logger.error(f"Failed to extract EPUB metadata: {e}")
        return {}
