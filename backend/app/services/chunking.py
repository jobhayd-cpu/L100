from __future__ import annotations

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Max characters per chunk; we try to stay on page boundaries
CHUNK_MAX_CHARS = 2000
CHUNK_OVERLAP_CHARS = 100


def chunk_pages(
    pages: List[Tuple[int, str]],
    max_chars: int = CHUNK_MAX_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> List[Tuple[int, int, str]]:
    """
    Split pages into chunks without mixing pages when possible.
    pages: list of (page_number_1based, text)
    Returns list of (page_from, page_to, chunk_text).
    Strategy:
      1. If a single page fits in max_chars, it becomes its own chunk.
      2. If a page is longer than max_chars, it is split into sub-chunks
         (all carrying the same page number).
      3. Pages are never merged across page boundaries.
    """
    chunks: List[Tuple[int, int, str]] = []

    for page_num, text in pages:
        if not text or not text.strip():
            continue

        text = text.strip()

        if len(text) <= max_chars:
            chunks.append((page_num, page_num, text))
        else:
            # Split long page text into sub-chunks
            start = 0
            while start < len(text):
                end = min(start + max_chars, len(text))
                sub = text[start:end]
                chunks.append((page_num, page_num, sub))
                start = end - overlap_chars
                if start <= 0:
                    break

    return chunks
