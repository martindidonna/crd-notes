from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    index: int
    start_word: int
    end_word: int


def chunk_text(text: str, *, size: int, overlap: int) -> list[TextChunk]:
    words = _words(text)
    if not words:
        return []
    safe_size = max(40, min(500, size))
    safe_overlap = max(0, min(safe_size - 1, overlap))
    step = max(1, safe_size - safe_overlap)
    chunks: list[TextChunk] = []
    for start in range(0, len(words), step):
        end = min(start + safe_size, len(words))
        chunk_words = words[start:end]
        if not chunk_words:
            continue
        cleaned = clean_text(" ".join(chunk_words))
        if cleaned:
            chunks.append(
                TextChunk(
                    text=cleaned,
                    index=len(chunks),
                    start_word=start,
                    end_word=end,
                )
            )
        if end >= len(words):
            break
    return chunks


def clean_text(value: str, *, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit].strip()


def _words(text: str) -> list[str]:
    return clean_text(text, limit=max(len(text), 4000)).split()
