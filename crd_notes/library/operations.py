from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from crd_notes.core.errors import LibraryError
from crd_notes.library.models import OperationItem, OperationKind, OperationSource, OperationStatus
from crd_notes.library.repository import LibraryRepository, utc_now


@dataclass(frozen=True)
class ParsedOperation:
    kind: OperationKind
    text: str
    owner: str = ""
    due_date: date | None = None


SECTION_KIND_RULES: tuple[tuple[OperationKind, tuple[str, ...]], ...] = (
    ("decision", ("decision", "decisioni prese", "decisioni del party")),
    ("action", ("azioni", "responsabilita", "piano operativo", "prossimi passi", "task")),
    ("risk", ("rischi", "blocchi", "rischio", "blocco")),
    ("question", ("domande aperte", "chiarimenti", "quesiti")),
)

AI_EXTRACTION_PROMPT = """Sei un assistente operativo. Estrai dal summary solo elementi tracciabili.

Rispondi esclusivamente con JSON valido, senza markdown:
{
  "items": [
    {
      "kind": "action|decision|risk|question",
      "text": "testo breve e completo",
      "owner": "responsabile se presente, altrimenti stringa vuota",
      "due_date": "YYYY-MM-DD se presente, altrimenti null"
    }
  ]
}

Regole:
- non inventare dettagli;
- ignora segnaposto come [Owner], [Scadenza], [INCERTO] se non contengono valori reali;
- usa "action" per task/prossimi passi, "decision" per decisioni, "risk" per rischi/blocchi, "question" per domande aperte;
- mantieni ogni elemento sotto 220 caratteri.
"""


class OperationService:
    def __init__(self, repository: LibraryRepository) -> None:
        self.repository = repository

    def extract_from_latest_summary(self, entry_id: str) -> list[OperationItem]:
        summary = self._latest_summary(entry_id)
        existing = self.repository.list_operation_items(summary_id=summary.id, source="summary")
        if existing:
            return existing

        parsed = parse_summary_operations(summary.content)
        items = self._items_from_parsed(
            entry_id=entry_id,
            summary_id=summary.id,
            source="summary",
            parsed=parsed,
        )
        self.repository.add_operation_items(items)
        return self.repository.list_operation_items(summary_id=summary.id, source="summary")

    def replace_ai_extraction(self, entry_id: str, raw_json: str) -> list[OperationItem]:
        summary = self._latest_summary(entry_id)
        parsed = parse_ai_operations(raw_json)
        items = self._items_from_parsed(
            entry_id=entry_id,
            summary_id=summary.id,
            source="ai",
            parsed=parsed,
        )
        self.repository.delete_operation_items(entry_id=entry_id, summary_id=summary.id, source="ai")
        self.repository.add_operation_items(items)
        return self.repository.list_operation_items(summary_id=summary.id, source="ai")

    def update_item(
        self,
        item_id: str,
        *,
        text: str | None = None,
        owner: str | None = None,
        due_date: date | None = None,
        status: OperationStatus | None = None,
    ) -> OperationItem:
        if text is not None and not text.strip():
            raise LibraryError("Il testo dell'elemento operativo non puo' essere vuoto.")
        if status is not None and status not in {"open", "done"}:
            raise LibraryError("Stato elemento operativo non valido.")
        item = self.repository.update_operation_item(
            item_id,
            text=text.strip() if text is not None else None,
            owner=owner.strip() if owner is not None else None,
            due_date=due_date,
            status=status,
        )
        if item is None:
            raise LibraryError("Elemento operativo non trovato.")
        return item

    def _latest_summary(self, entry_id: str):
        if self.repository.get_entry(entry_id) is None:
            raise LibraryError("Trascrizione non trovata.")
        summaries = self.repository.list_summaries(entry_id)
        if not summaries:
            raise LibraryError("Nessun riassunto disponibile per questa trascrizione.")
        return summaries[0]

    def _items_from_parsed(
        self,
        *,
        entry_id: str,
        summary_id: str,
        source: OperationSource,
        parsed: list[ParsedOperation],
    ) -> list[OperationItem]:
        now = utc_now()
        seen: set[tuple[str, str]] = set()
        items: list[OperationItem] = []
        for parsed_item in parsed:
            text = _clean_text(parsed_item.text)
            if not text or _is_placeholder(text):
                continue
            key = (parsed_item.kind, _fingerprint(text))
            if key in seen:
                continue
            seen.add(key)
            items.append(
                OperationItem(
                    id=str(uuid4()),
                    entry_id=entry_id,
                    summary_id=summary_id,
                    kind=parsed_item.kind,
                    text=text,
                    owner="" if _is_placeholder(parsed_item.owner) else parsed_item.owner.strip(),
                    due_date=parsed_item.due_date,
                    status="open",
                    source=source,
                    created_at=now,
                    updated_at=now,
                )
            )
        return items


def parse_summary_operations(content: str) -> list[ParsedOperation]:
    current_kind: OperationKind | None = None
    parsed: list[ParsedOperation] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading_kind = _heading_kind(line)
        if heading_kind:
            current_kind = heading_kind
            continue
        if current_kind is None:
            continue
        bullet = _strip_bullet(line)
        if not bullet or _looks_like_subheading(bullet):
            continue
        item_kind = _line_kind(bullet) or current_kind
        if item_kind == "action":
            parsed.append(_parse_action_line(bullet))
        else:
            parsed.append(ParsedOperation(kind=item_kind, text=_remove_label_prefix(bullet)))
    return parsed


def parse_ai_operations(raw_json: str) -> list[ParsedOperation]:
    try:
        data = json.loads(_extract_json(raw_json))
    except json.JSONDecodeError as exc:
        raise LibraryError("Risposta AI non valida.", detail="L'estrazione operativa non contiene JSON valido.") from exc

    raw_items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(raw_items, list):
        raise LibraryError("Risposta AI non valida.", detail="Campo items mancante o non valido.")

    parsed: list[ParsedOperation] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        text = str(item.get("text") or "").strip()
        if kind not in {"action", "decision", "risk", "question"} or not text:
            continue
        parsed.append(
            ParsedOperation(
                kind=kind,
                text=text,
                owner=str(item.get("owner") or "").strip(),
                due_date=_parse_due_date(item.get("due_date")),
            )
        )
    return parsed


def _heading_kind(line: str) -> OperationKind | None:
    normalized = _normalize(line)
    if not re.match(r"^(#{1,6}\s*)?(\d+[\).]\s*)?[a-z]", normalized):
        return None
    for kind, tokens in SECTION_KIND_RULES:
        if any(token in normalized for token in tokens):
            return kind
    return None


def _strip_bullet(line: str) -> str:
    return re.sub(r"^(\s*[-*+]|\d+[\).])\s+", "", line).strip()


def _line_kind(line: str) -> OperationKind | None:
    normalized = _normalize(line)
    if re.match(r"^(domanda|quesito|chiarimento|chiarimento necessario)\s*:", normalized):
        return "question"
    if re.match(r"^(rischio|blocco|problema)\s*:", normalized):
        return "risk"
    if re.match(r"^(decisione)\s*:", normalized):
        return "decision"
    if re.match(r"^(azione|task)\s*:", normalized):
        return "action"
    return None


def _looks_like_subheading(line: str) -> bool:
    normalized = _normalize(line).strip(":")
    labels = {
        "decisione",
        "motivazione",
        "impatto",
        "azione",
        "responsabile",
        "scadenza",
        "stato",
        "rischio",
        "blocco",
        "chiarimento necessario",
    }
    return normalized in labels


def _parse_action_line(line: str) -> ParsedOperation:
    parts = [part.strip(" []") for part in re.split(r"\s+-\s+", line) if part.strip(" []")]
    if len(parts) >= 2:
        text = _remove_label_prefix(parts[0])
        owner = "" if len(parts) < 2 else parts[1]
        due_date = _parse_due_date(parts[2]) if len(parts) >= 3 else None
        return ParsedOperation(kind="action", text=text, owner=owner, due_date=due_date)
    return ParsedOperation(kind="action", text=_remove_label_prefix(line))


def _remove_label_prefix(text: str) -> str:
    return re.sub(
        r"^(decisione|azione|task|rischio|blocco|domanda|quesito|chiarimento necessario|problema|mitigazione)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _parse_due_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if _is_placeholder(text):
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


def _extract_json(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    start = min([idx for idx in (text.find("{"), text.find("[")) if idx >= 0], default=0)
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start : end + 1] if end >= start else text


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" -")
    return text[:320].strip()


def _fingerprint(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize(value)).strip()


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _is_placeholder(value: str) -> bool:
    text = _normalize(value).strip(" []:-")
    return not text or text in {
        "owner",
        "responsabile",
        "scadenza",
        "dipendenze",
        "priorita",
        "stato",
        "incerto",
        "n/a",
        "non indicato",
        "non presente",
    }
