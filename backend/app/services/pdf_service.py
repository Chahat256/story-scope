import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean extracted PDF text of common artifacts."""
    # Normalize whitespace
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)

    # Remove excessive blank lines (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove hyphenation at line breaks (common in PDFs)
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

    # Fix common OCR/extraction issues
    text = re.sub(r'[ \t]{2,}', ' ', text)

    # Remove page headers/footers patterns (basic heuristic)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip very short lines that look like page numbers
        if re.match(r'^\d+$', stripped) and len(stripped) <= 4:
            continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()


def extract_text_from_pdf(pdf_path: str) -> List[Tuple[int, str]]:
    """
    Extract text from a PDF file, returning list of (page_number, text) tuples.
    Page numbers are 1-indexed.
    """
    pages = []

    try:
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            if text.strip():  # Only include non-empty pages
                cleaned = clean_text(text)
                if cleaned:
                    pages.append((page_num + 1, cleaned))

        doc.close()
        logger.info(f"Extracted {len(pages)} pages from {pdf_path}")
        return pages

    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        raise


def get_pdf_metadata(pdf_path: str) -> dict:
    """Extract metadata from PDF."""
    try:
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        page_count = len(doc)
        doc.close()

        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "page_count": page_count,
            "format": metadata.get("format", ""),
        }
    except Exception as e:
        logger.error(f"Failed to extract metadata: {e}")
        return {}


def validate_pdf(pdf_path: str) -> Tuple[bool, str]:
    """Validate that the file is a readable PDF with extractable text."""
    try:
        doc = fitz.open(pdf_path)

        if len(doc) == 0:
            return False, "PDF appears to be empty."

        # Check first few pages for text content
        text_pages = 0
        for i in range(min(5, len(doc))):
            page = doc[i]
            if page.get_text("text").strip():
                text_pages += 1

        doc.close()

        if text_pages == 0:
            return False, "This PDF does not appear to contain extractable text. StoryScope works best with digital text PDFs, not scanned images."

        return True, "Valid"

    except Exception as e:
        return False, f"Could not read PDF: {str(e)}"
