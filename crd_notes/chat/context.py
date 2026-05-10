from __future__ import annotations

import re
from dataclasses import dataclass

from crd_notes.library.models import ChatMessage
from crd_notes.rag import RagChunk


HISTORY_MESSAGE_LIMIT = 6
HISTORY_MAX_CHARS = 1400
QUERY_HISTORY_CHARS = 700
CHUNK_TEXT_LIMIT = 520
MIN_CHUNK_SCORE = 0.08
MAX_CHUNKS_PER_SOURCE = 2


@dataclass(frozen=True)
class CompactedContext:
    chunks: list[RagChunk]
    text: str
    evidence: str


def build_retrieval_query(
    *,
    user_message: str,
    history: list[ChatMessage],
    mentioned_titles: list[str],
    mentioned_folders: list[str],
) -> str:
    parts = [user_message.strip()]
    recent_user_context = " ".join(
        message.content.strip()
        for message in history[-HISTORY_MESSAGE_LIMIT:]
        if message.role == "user" and message.content.strip()
    )
    if recent_user_context:
        parts.append(_clip(recent_user_context, QUERY_HISTORY_CHARS))
    if mentioned_titles:
        parts.append("Riunioni taggate: " + ", ".join(mentioned_titles))
    if mentioned_folders:
        parts.append("Folder knowledge taggati: " + ", ".join(mentioned_folders))
    return _clean(" ".join(parts))


def compact_history(messages: list[ChatMessage]) -> str:
    lines: list[str] = []
    remaining = HISTORY_MAX_CHARS
    user_messages = [message for message in messages if message.role == "user"]
    for message in reversed(user_messages[-HISTORY_MESSAGE_LIMIT:]):
        role = "Utente"
        text = _clip(message.content, min(360, max(120, remaining)))
        line = f"{role}: {text}"
        if len(line) > remaining:
            break
        lines.append(line)
        remaining -= len(line) + 1
    return "\n".join(reversed(lines))


def compact_chunks(chunks: list[RagChunk], *, max_chars: int) -> CompactedContext:
    selected: list[RagChunk] = []
    seen_texts: set[str] = set()
    source_counts: dict[tuple[str, str], int] = {}

    for chunk in sorted(chunks, key=lambda item: item.score, reverse=True):
        if chunk.score < MIN_CHUNK_SCORE:
            continue
        text_key = _fingerprint(chunk.text)
        if text_key in seen_texts:
            continue
        source_key = (chunk.entry_id, chunk.doc_type)
        if source_counts.get(source_key, 0) >= MAX_CHUNKS_PER_SOURCE:
            continue
        seen_texts.add(text_key)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        selected.append(
            RagChunk(
                text=_clip(chunk.text, CHUNK_TEXT_LIMIT),
                score=chunk.score,
                entry_id=chunk.entry_id,
                entry_title=chunk.entry_title,
                doc_type=chunk.doc_type,
                source=chunk.source,
            )
        )

    lines: list[str] = []
    total = 0
    final_chunks: list[RagChunk] = []
    for index, chunk in enumerate(selected, start=1):
        title = chunk.entry_title or "Documento del workspace"
        line = f"Estratto {index} - {title}\n{chunk.text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        final_chunks.append(chunk)
        total += len(line) + 1

    return CompactedContext(
        chunks=final_chunks,
        text="\n".join(lines),
        evidence=_evidence_text(final_chunks),
    )


def extract_followups(content: str) -> list[str]:
    marker = re.search(
        r"(?:domande successive|prossime domande|potresti chiedere)[:\n]+(.+)$",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not marker:
        return []
    candidates = []
    for line in marker.group(1).splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if cleaned.endswith("?") and 8 <= len(cleaned) <= 180:
            candidates.append(cleaned)
    return candidates[:4]


def clean_assistant_content(content: str) -> str:
    cleaned = _normalize_model_output(content)
    cleaned = _remove_rag_section_labels(cleaned)
    cleaned = _remove_markdown_table_separators(cleaned)
    return cleaned.strip()


def _evidence_text(chunks: list[RagChunk]) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks[:5], start=1):
        title = chunk.entry_title or "Documento del workspace"
        lines.append(
            f"{index}. {title}: {_clip(chunk.text, 320)}"
        )
    return "\n".join(lines)


def _clip(value: str, limit: int) -> str:
    cleaned = _clean(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _fingerprint(value: str) -> str:
    return _clean(value).lower()[:240]


def _normalize_model_output(content: str) -> str:
    value = str(content or "")
    value = re.sub(r"<\s*br\s*/?\s*>", "\n", value, flags=re.IGNORECASE)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value


def _remove_rag_section_labels(content: str) -> str:
    lines: list[str] = []
    for line in content.splitlines():
        cleaned = re.sub(
            r"^\s*(?:#+\s*)?(?:supportato\s+dal\s+rag|incerto|incertezze)\s*:\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\bRAG\s*#\d+\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bRAG\b", "materiale del workspace", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned:
            lines.append(cleaned)
        elif lines and lines[-1]:
            lines.append("")
    return "\n".join(lines)


def _remove_markdown_table_separators(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", line):
            continue
        lines.append(line)
    return "\n".join(lines)
