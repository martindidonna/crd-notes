from __future__ import annotations

import json
import re
from dataclasses import dataclass

from crd_notes.core.errors import LibraryError
from crd_notes.library.models import Summary, SummaryMetadata
from crd_notes.library.repository import LibraryRepository, utc_now


SUMMARY_METADATA_PROMPT = """Sei un analista che arricchisce i riassunti di call per ricerca e continuita' di contesto.

Rispondi esclusivamente con JSON valido, senza markdown:
{
  "tags": ["3-8 tag brevi"],
  "keywords": ["8-16 parole chiave utili alla ricerca"],
  "people": ["persone o ruoli citati"],
  "topics": ["temi o aree funzionali"],
  "context": "5-8 frasi che ampliano il contesto: cosa conta, perche', quali elementi vanno ricordati nel workspace"
}

Adatta l'estrazione alla tipologia indicata. Non inventare nomi, date o decisioni. Usa italiano diretto.
"""


@dataclass(frozen=True)
class ParsedSummaryMetadata:
    tags: list[str]
    keywords: list[str]
    people: list[str]
    topics: list[str]
    context: str


class SummaryMetadataService:
    def __init__(self, repository: LibraryRepository) -> None:
        self.repository = repository

    def save_from_ai(self, *, summary: Summary, raw_json: str) -> SummaryMetadata:
        parsed = parse_summary_metadata(raw_json)
        now = utc_now()
        metadata = SummaryMetadata(
            summary_id=summary.id,
            entry_id=summary.entry_id,
            tags=parsed.tags,
            keywords=parsed.keywords,
            people=parsed.people,
            topics=parsed.topics,
            context=parsed.context,
            created_at=now,
            updated_at=now,
        )
        self.repository.add_summary_metadata(metadata)
        return metadata


def build_summary_metadata_input(*, prompt_id: str, title: str, summary: str) -> str:
    return f"Tipologia call: {prompt_id}\nTitolo: {title}\n\nRiassunto:\n{summary}"


def parse_summary_metadata(raw_json: str) -> ParsedSummaryMetadata:
    try:
        data = json.loads(_extract_json(raw_json))
    except json.JSONDecodeError as exc:
        raise LibraryError("Metadati summary non validi.", detail="La risposta AI non contiene JSON valido.") from exc
    if not isinstance(data, dict):
        raise LibraryError("Metadati summary non validi.", detail="La risposta AI deve essere un oggetto JSON.")
    return ParsedSummaryMetadata(
        tags=_clean_list(data.get("tags"), limit=8),
        keywords=_clean_list(data.get("keywords"), limit=16),
        people=_clean_list(data.get("people"), limit=16),
        topics=_clean_list(data.get("topics"), limit=12),
        context=_clean_text(str(data.get("context") or ""), limit=1200),
    )


def _clean_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(str(item), limit=72)
        if text and text.lower() not in {existing.lower() for existing in cleaned}:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clean_text(value: str, *, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip(" -")[:limit].strip()


def _extract_json(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    return text[start : end + 1] if start >= 0 and end >= start else text
