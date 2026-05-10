from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from crd_notes.library.models import DEFAULT_WORKSPACE_ID, LibraryEntry, OperationItem, Summary
from crd_notes.library.repository import LibraryRepository


WORKSPACE_BRIEF_PROMPT = """Sei un Chief of Staff operativo.

Ricevi un quadro workspace calcolato localmente con frequenze, cluster, decisioni, rischi e domande.
Produci un brief sintetico in italiano, senza inventare dati:
- 1 paragrafo di contesto attuale
- 3-5 priorita' concrete
- 3 rischi o punti di attenzione se presenti
- prossima azione consigliata

Rispondi in testo compatto con righe brevi e titoli semplici. Non ripetere liste vuote.
"""

_STOPWORDS = {
    "alla",
    "allo",
    "anche",
    "avere",
    "come",
    "con",
    "cosa",
    "dalla",
    "delle",
    "degli",
    "dell",
    "del",
    "dei",
    "dove",
    "essere",
    "fare",
    "gli",
    "nel",
    "nella",
    "per",
    "piu",
    "che",
    "non",
    "sono",
    "sul",
    "sulla",
    "tra",
    "una",
    "uno",
    "the",
    "and",
    "for",
    "with",
}


@dataclass(frozen=True)
class IntelligenceItem:
    text: str
    score: float
    count: int


@dataclass(frozen=True)
class IntelligenceCluster:
    id: str
    title: str
    terms: list[str]
    entry_ids: list[str]
    entry_titles: list[str]
    score: float


@dataclass(frozen=True)
class TimelineDecision:
    text: str
    entry_id: str
    entry_title: str
    recorded_on: date | None
    created_at: datetime


@dataclass(frozen=True)
class WorkspaceIntelligence:
    workspace_id: str
    generated_at: datetime
    entry_count: int
    summary_count: int
    operation_open_count: int
    top_tags: list[IntelligenceItem]
    top_keywords: list[IntelligenceItem]
    top_people: list[IntelligenceItem]
    top_topics: list[IntelligenceItem]
    clusters: list[IntelligenceCluster]
    decisions: list[TimelineDecision]
    risks: list[TimelineDecision]
    questions: list[TimelineDecision]
    local_brief: str


class WorkspaceIntelligenceService:
    def __init__(self, repository: LibraryRepository) -> None:
        self.repository = repository

    def build(self, workspace_id: str | None = None) -> WorkspaceIntelligence:
        workspace_id = workspace_id or DEFAULT_WORKSPACE_ID
        entries = self.repository.list_entries(workspace_id)
        entry_map = {entry.id: entry for entry in entries}
        metadata = self.repository.entry_metadata()
        summaries_by_entry = {
            entry.id: self.repository.list_summaries(entry.id)
            for entry in entries
        }
        operations = self.repository.list_operation_items(workspace_id=workspace_id)
        generated_at = datetime.now().astimezone()

        tag_counts: Counter[str] = Counter()
        keyword_counts: Counter[str] = Counter()
        people_counts: Counter[str] = Counter()
        topic_counts: Counter[str] = Counter()
        for entry in entries:
            item = metadata.get(entry.id, {})
            tag_counts.update(_normalize_items(item.get("tags", [])))
            keyword_counts.update(_normalize_items(item.get("keywords", [])))
            people_counts.update(_normalize_items([*entry.participants, *item.get("people", [])]))
            topic_counts.update(_normalize_items(item.get("topics", [])))

        clusters = _cluster_entries(entries, metadata, summaries_by_entry)
        decisions = _operation_timeline("decision", operations, entry_map, limit=10)
        risks = _operation_timeline("risk", operations, entry_map, limit=8, open_only=True)
        questions = _operation_timeline("question", operations, entry_map, limit=8, open_only=True)
        summary_count = sum(len(items) for items in summaries_by_entry.values())
        open_count = sum(1 for item in operations if item.status == "open")

        return WorkspaceIntelligence(
            workspace_id=workspace_id,
            generated_at=generated_at,
            entry_count=len(entries),
            summary_count=summary_count,
            operation_open_count=open_count,
            top_tags=_top_items(tag_counts),
            top_keywords=_top_items(keyword_counts),
            top_people=_top_items(people_counts),
            top_topics=_top_items(topic_counts),
            clusters=clusters,
            decisions=decisions,
            risks=risks,
            questions=questions,
            local_brief=_local_brief(
                entry_count=len(entries),
                summary_count=summary_count,
                clusters=clusters,
                tags=tag_counts,
                risks=risks,
                questions=questions,
                open_count=open_count,
            ),
        )


def build_workspace_brief_input(intelligence: WorkspaceIntelligence) -> str:
    return json.dumps(
        {
            "workspace_id": intelligence.workspace_id,
            "entry_count": intelligence.entry_count,
            "summary_count": intelligence.summary_count,
            "operation_open_count": intelligence.operation_open_count,
            "top_tags": [item.text for item in intelligence.top_tags],
            "top_keywords": [item.text for item in intelligence.top_keywords],
            "top_people": [item.text for item in intelligence.top_people],
            "top_topics": [item.text for item in intelligence.top_topics],
            "clusters": [
                {
                    "title": cluster.title,
                    "terms": cluster.terms,
                    "entries": cluster.entry_titles,
                }
                for cluster in intelligence.clusters
            ],
            "decisions": [item.text for item in intelligence.decisions],
            "risks": [item.text for item in intelligence.risks],
            "questions": [item.text for item in intelligence.questions],
            "local_brief": intelligence.local_brief,
        },
        ensure_ascii=False,
    )


def _normalize_items(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item)).strip(" -").lower()
        if text:
            cleaned.append(text)
    return cleaned


def _top_items(counter: Counter[str], *, limit: int = 10) -> list[IntelligenceItem]:
    if not counter:
        return []
    max_count = max(counter.values())
    return [
        IntelligenceItem(text=text, count=count, score=round(count / max_count, 3))
        for text, count in counter.most_common(limit)
    ]


def _cluster_entries(
    entries: list[LibraryEntry],
    metadata: dict[str, dict[str, list[str] | str]],
    summaries_by_entry: dict[str, list[Summary]],
) -> list[IntelligenceCluster]:
    documents = {
        entry.id: _entry_document(entry, metadata.get(entry.id, {}), summaries_by_entry.get(entry.id, []))
        for entry in entries
    }
    tokenized = {entry_id: _tokens(text) for entry_id, text in documents.items()}
    if not tokenized:
        return []
    doc_freq: Counter[str] = Counter()
    for tokens in tokenized.values():
        doc_freq.update(set(tokens))

    vectors = {
        entry_id: _tfidf(tokens, doc_freq, len(tokenized))
        for entry_id, tokens in tokenized.items()
    }
    components = _similar_components(vectors)
    entry_map = {entry.id: entry for entry in entries}
    clusters: list[IntelligenceCluster] = []
    for index, component in enumerate(components, start=1):
        term_scores: Counter[str] = Counter()
        for entry_id in component:
            term_scores.update(vectors[entry_id])
        terms = [term for term, _score in term_scores.most_common(5)]
        titles = [entry_map[entry_id].title for entry_id in component if entry_id in entry_map]
        if not terms or not titles:
            continue
        clusters.append(
            IntelligenceCluster(
                id=f"cluster-{index}",
                title=", ".join(terms[:3]),
                terms=terms,
                entry_ids=component,
                entry_titles=titles[:6],
                score=round(sum(term_scores.values()), 3),
            )
        )
    return sorted(clusters, key=lambda item: (len(item.entry_ids), item.score), reverse=True)[:6]


def _entry_document(
    entry: LibraryEntry,
    metadata: dict[str, list[str] | str],
    summaries: list[Summary],
) -> str:
    metadata_parts: list[str] = []
    for field in ("tags", "keywords", "people", "topics"):
        value = metadata.get(field, [])
        if isinstance(value, list):
            metadata_parts.extend(str(item) for item in value)
    context = metadata.get("context", "")
    summary_text = " ".join(summary.content[:1800] for summary in summaries[:2])
    return " ".join(
        [
            entry.title,
            entry.notes,
            " ".join(entry.participants),
            " ".join(metadata_parts),
            str(context),
            summary_text,
        ]
    )


def _tokens(text: str) -> list[str]:
    normalized = (
        text.lower()
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in _STOPWORDS
    ]


def _tfidf(tokens: list[str], doc_freq: Counter[str], total_docs: int) -> dict[str, float]:
    counts = Counter(tokens)
    if not counts:
        return {}
    total = sum(counts.values())
    vector = {}
    for token, count in counts.items():
        tf = count / total
        idf = math.log((1 + total_docs) / (1 + doc_freq[token])) + 1
        vector[token] = tf * idf
    return vector


def _similar_components(vectors: dict[str, dict[str, float]]) -> list[list[str]]:
    ids = list(vectors)
    links: dict[str, set[str]] = defaultdict(set)
    for left_index, left_id in enumerate(ids):
        for right_id in ids[left_index + 1 :]:
            similarity = _cosine(vectors[left_id], vectors[right_id])
            if similarity >= 0.14:
                links[left_id].add(right_id)
                links[right_id].add(left_id)
    seen: set[str] = set()
    components: list[list[str]] = []
    for entry_id in ids:
        if entry_id in seen:
            continue
        stack = [entry_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(links[current] - seen)
        components.append(component)
    return components


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _operation_timeline(
    kind: str,
    operations: list[OperationItem],
    entries: dict[str, LibraryEntry],
    *,
    limit: int,
    open_only: bool = False,
) -> list[TimelineDecision]:
    items = [
        item
        for item in operations
        if item.kind == kind and (not open_only or item.status == "open")
    ]
    items.sort(
        key=lambda item: (
            (entries.get(item.entry_id).recorded_on if entries.get(item.entry_id) else None)
            or date.min,
            item.created_at,
        ),
        reverse=True,
    )
    timeline = []
    for item in items[:limit]:
        entry = entries.get(item.entry_id)
        if not entry:
            continue
        timeline.append(
            TimelineDecision(
                text=item.text,
                entry_id=entry.id,
                entry_title=entry.title,
                recorded_on=entry.recorded_on,
                created_at=item.created_at,
            )
        )
    return timeline


def _local_brief(
    *,
    entry_count: int,
    summary_count: int,
    clusters: list[IntelligenceCluster],
    tags: Counter[str],
    risks: list[TimelineDecision],
    questions: list[TimelineDecision],
    open_count: int,
) -> str:
    if entry_count == 0:
        return "Workspace vuoto. Importa o genera una trascrizione per creare il quadro operativo."
    main_topics = ", ".join(text for text, _count in tags.most_common(4)) or "temi non ancora classificati"
    cluster_text = clusters[0].title if clusters else main_topics
    return (
        f"Il workspace contiene {entry_count} trascrizioni e {summary_count} riassunti. "
        f"Il fuoco principale emerge su {cluster_text}. "
        f"Gli elementi operativi aperti sono {open_count}; "
        f"rischi aperti: {len(risks)}, domande aperte: {len(questions)}. "
        f"Usa i cluster e la timeline decisionale per ricostruire rapidamente lo stato del contesto."
    )
