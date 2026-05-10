from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from crd_notes.core.config import AppSettings, RagSettings
from crd_notes.core.errors import ConfigurationError
from crd_notes.core.paths import DATA_DIR, RAG_DIR
from crd_notes.knowledge import ExtractedDocument, extract_document_from_file
from crd_notes.library.models import LibraryEntry, WorkspaceKnowledgeFile
from crd_notes.library.repository import LibraryRepository
from crd_notes.rag.chunking import chunk_text, clean_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagChunk:
    text: str
    score: float
    entry_id: str
    entry_title: str
    doc_type: str
    source: str


@dataclass(frozen=True)
class RagContext:
    chunks: list[RagChunk]
    context_text: str


@dataclass(frozen=True)
class _RagDoc:
    id: str
    text: str
    metadata: dict[str, str | int | float | bool]


class RagService:
    def __init__(self, repository: LibraryRepository) -> None:
        self.repository = repository
        self._lock = RLock()
        self._clients: dict[Path, object] = {}
        self._models: dict[str, object] = {}

    def index_entry(self, entry_id: str, settings: AppSettings) -> None:
        if not settings.rag.enabled:
            return
        entry = self.repository.get_entry(entry_id)
        if not entry:
            return
        docs = self._build_entry_docs(entry=entry, settings=settings)
        collection = self._collection(entry.workspace_id, settings.rag)
        collection.delete(where={"entry_id": entry.id})
        self.repository.replace_rag_keyword_docs(
            workspace_id=entry.workspace_id,
            entry_id=entry.id,
            docs=[_keyword_doc(doc) for doc in docs],
        )
        if not docs:
            return
        texts = [doc.text for doc in docs]
        embeddings = self._embed_documents(texts, settings.rag)
        collection.add(
            ids=[doc.id for doc in docs],
            documents=texts,
            metadatas=[doc.metadata for doc in docs],
            embeddings=embeddings,
        )

    def index_workspace_knowledge_file(self, knowledge_file_id: str, settings: AppSettings) -> None:
        if not settings.rag.enabled:
            return
        knowledge_file = self.repository.get_workspace_knowledge_file(knowledge_file_id)
        if not knowledge_file:
            return
        path = Path(knowledge_file.stored_path)
        if not path.exists():
            self.repository.update_workspace_knowledge_file_status(
                knowledge_file.id,
                status="failed",
                error="File knowledge base non trovato nello storage locale.",
            )
            return
        try:
            self.repository.update_workspace_knowledge_file_status(
                knowledge_file.id,
                status="pending",
                error="Indicizzazione in corso.",
            )
            extracted = extract_document_from_file(path)
            docs = _chunk_knowledge_file_to_docs(
                knowledge_file=knowledge_file,
                document=extracted,
                rag=settings.rag,
            )
            if not docs:
                self.repository.update_workspace_knowledge_file_status(
                    knowledge_file.id,
                    status="failed",
                    error="Nessun contenuto testuale estratto dal file.",
                )
                return
            texts = [doc.text for doc in docs]
            embeddings = self._embed_documents(texts, settings.rag)
            collection = self._collection(knowledge_file.workspace_id, settings.rag)
            collection.delete(where={"knowledge_file_id": knowledge_file.id})
            collection.add(
                ids=[doc.id for doc in docs],
                documents=texts,
                metadatas=[doc.metadata for doc in docs],
                embeddings=embeddings,
            )
            self.repository.replace_rag_keyword_knowledge_docs(
                workspace_id=knowledge_file.workspace_id,
                knowledge_file_id=knowledge_file.id,
                docs=[_keyword_doc(doc) for doc in docs],
            )
            self.repository.update_workspace_knowledge_file_status(
                knowledge_file.id,
                status="indexed",
                error="; ".join(extracted.warnings),
            )
        except Exception as exc:
            logger.exception("Indicizzazione knowledge file fallita: %s", knowledge_file.id)
            self.repository.update_workspace_knowledge_file_status(
                knowledge_file.id,
                status="failed",
                error=clean_text(str(exc), limit=300) or "Errore durante l'indicizzazione del file.",
            )

    def remove_workspace_knowledge_file(
        self,
        *,
        knowledge_file: WorkspaceKnowledgeFile,
        settings: AppSettings,
    ) -> None:
        if not settings.rag.enabled:
            return
        collection = self._collection(knowledge_file.workspace_id, settings.rag)
        collection.delete(where={"knowledge_file_id": knowledge_file.id})
        self.repository.delete_rag_keyword_docs(
            workspace_id=knowledge_file.workspace_id,
            entry_id=knowledge_file.id,
        )

    def reindex_workspace(self, workspace_id: str, settings: AppSettings) -> None:
        if not settings.rag.enabled:
            return
        collection = self._collection(workspace_id, settings.rag)
        collection.delete(where={})
        self.repository.clear_workspace_rag_keyword_docs(workspace_id)
        for entry in self.repository.list_entries(workspace_id):
            self.index_entry(entry.id, settings)
        for knowledge_file in self.repository.list_workspace_knowledge_files(workspace_id):
            self.index_workspace_knowledge_file(knowledge_file.id, settings)

    def build_context(
        self,
        *,
        workspace_id: str,
        query_text: str,
        settings: AppSettings,
        doc_types: list[str] | None = None,
        entry_ids: list[str] | None = None,
        knowledge_folders: list[str] | None = None,
        top_k: int | None = None,
        candidate_k: int | None = None,
    ) -> RagContext:
        if not settings.rag.enabled:
            return RagContext(chunks=[], context_text="")
        cleaned_query = clean_text(query_text)
        if not cleaned_query:
            return RagContext(chunks=[], context_text="")
        collection = self._collection(workspace_id, settings.rag)
        where = _build_where_filter(
            doc_types=doc_types,
            entry_ids=entry_ids,
            knowledge_folders=knowledge_folders,
        )

        embedding = self._embed_query(cleaned_query, settings.rag)
        n_results = candidate_k or top_k or settings.rag.top_k
        result = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        chunks: list[RagChunk] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else 1.0
            chunk = RagChunk(
                text=clean_text(document, limit=700),
                score=max(0.0, 1 - float(distance or 0.0)),
                entry_id=str(metadata.get("entry_id") or metadata.get("knowledge_file_id") or ""),
                entry_title=str(metadata.get("entry_title") or metadata.get("knowledge_file_name") or ""),
                doc_type=str(metadata.get("doc_type") or ""),
                source=str(metadata.get("source") or ""),
            )
            if chunk.text:
                chunks.append(chunk)

        if settings.rag.hybrid_keyword_enabled:
            chunks.extend(
                self._keyword_chunks(
                    workspace_id=workspace_id,
                    query_text=cleaned_query,
                    doc_types=doc_types,
                    entry_ids=entry_ids,
                    knowledge_folders=knowledge_folders,
                    limit=n_results,
                )
            )

        chunks = self._rerank_chunks(
            query_text=cleaned_query,
            chunks=_dedupe_chunks(chunks),
            settings=settings,
        )[: top_k or settings.rag.top_k]
        return RagContext(chunks=chunks, context_text=_build_context_text(chunks, settings.rag))

    def _build_entry_docs(self, *, entry: LibraryEntry, settings: AppSettings) -> list[_RagDoc]:
        metadata_by_summary = self.repository.list_summary_metadata(entry.id)
        summaries = self.repository.list_summaries(entry.id)
        operations = self.repository.list_operation_items(entry_id=entry.id)
        docs: list[_RagDoc] = []

        docs.extend(
            _chunk_to_docs(
                prefix=f"entry:{entry.id}:transcript",
                doc_type="transcript",
                source="trascrizione",
                text=entry.transcript,
                entry=entry,
                rag=settings.rag,
            )
        )

        note_text = _join_non_empty(
            [
                f"Titolo: {entry.title}",
                f"Note: {entry.notes}" if entry.notes else "",
                f"Partecipanti: {', '.join(entry.participants)}" if entry.participants else "",
            ]
        )
        if note_text:
            docs.append(
                _RagDoc(
                    id=f"entry:{entry.id}:notes",
                    text=note_text,
                    metadata=_metadata(entry, doc_type="note", source="note entry", chunk_index=0),
                )
            )

        for summary in summaries:
            docs.extend(
                _chunk_to_docs(
                    prefix=f"entry:{entry.id}:summary:{summary.id}",
                    doc_type="summary",
                    source="riassunto",
                    text=summary.content,
                    entry=entry,
                    rag=settings.rag,
                )
            )
            metadata = metadata_by_summary.get(summary.id)
            if metadata:
                metadata_text = _join_non_empty(
                    [
                        f"Tag: {', '.join(metadata.tags)}" if metadata.tags else "",
                        f"Keywords: {', '.join(metadata.keywords)}" if metadata.keywords else "",
                        f"Persone: {', '.join(metadata.people)}" if metadata.people else "",
                        f"Temi: {', '.join(metadata.topics)}" if metadata.topics else "",
                        f"Contesto: {metadata.context}" if metadata.context else "",
                    ]
                )
                if metadata_text:
                    docs.append(
                        _RagDoc(
                            id=f"entry:{entry.id}:metadata:{summary.id}",
                            text=metadata_text,
                            metadata=_metadata(
                                entry,
                                doc_type="metadata",
                                source="metadati summary",
                                chunk_index=0,
                            ),
                        )
                    )

        for item in operations:
            text = _join_non_empty(
                [
                    f"Tipo: {item.kind}",
                    f"Stato: {item.status}",
                    f"Owner: {item.owner}" if item.owner else "",
                    f"Scadenza: {item.due_date.isoformat()}" if item.due_date else "",
                    f"Testo: {item.text}",
                ]
            )
            if text:
                docs.append(
                    _RagDoc(
                        id=f"entry:{entry.id}:operation:{item.id}",
                        text=text,
                        metadata=_metadata(entry, doc_type="operation", source="operativo", chunk_index=0),
                    )
                )
        return docs

    def _collection(self, workspace_id: str, rag: RagSettings):
        client = self._client(rag)
        name = _safe_collection_name(f"{rag.collection_prefix}_{workspace_id}")
        return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def _client(self, rag: RagSettings):
        path = _resolve_storage_path(rag)
        with self._lock:
            existing = self._clients.get(path)
            if existing is not None:
                return existing
            chromadb = _import_chromadb()
            client = chromadb.PersistentClient(path=str(path))
            self._clients[path] = client
            return client

    def _embed_documents(self, texts: list[str], rag: RagSettings) -> list[list[float]]:
        model = self._model(rag.embedding_model)
        prepared = [_embedding_text(text, is_query=False, model=rag.embedding_model) for text in texts]
        return model.encode(prepared, normalize_embeddings=True).tolist()

    def _embed_query(self, text: str, rag: RagSettings) -> list[float]:
        model = self._model(rag.embedding_model)
        prepared = _embedding_text(text, is_query=True, model=rag.embedding_model)
        return model.encode([prepared], normalize_embeddings=True).tolist()[0]

    def _model(self, model_name: str):
        with self._lock:
            existing = self._models.get(model_name)
            if existing is not None:
                return existing
            sentence_transformers = _import_sentence_transformers()
            model = sentence_transformers.SentenceTransformer(model_name)
            self._models[model_name] = model
            return model

    def _keyword_chunks(
        self,
        *,
        workspace_id: str,
        query_text: str,
        doc_types: list[str] | None,
        entry_ids: list[str] | None,
        knowledge_folders: list[str] | None,
        limit: int,
    ) -> list[RagChunk]:
        rows = self.repository.search_rag_keyword_docs(
            workspace_id=workspace_id,
            query=query_text,
            doc_types=doc_types,
            entry_ids=entry_ids,
            knowledge_folders=knowledge_folders,
            limit=limit,
        )
        chunks: list[RagChunk] = []
        for row in rows:
            rank = abs(float(row.get("rank") or 0.0))
            score = 1.0 / (1.0 + rank)
            chunks.append(
                RagChunk(
                    text=clean_text(str(row.get("content") or ""), limit=700),
                    score=score,
                    entry_id=str(row.get("entry_id") or ""),
                    entry_title=str(row.get("entry_title") or ""),
                    doc_type=str(row.get("doc_type") or ""),
                    source=str(row.get("source") or ""),
                )
            )
        return chunks

    def _rerank_chunks(
        self,
        *,
        query_text: str,
        chunks: list[RagChunk],
        settings: AppSettings,
    ) -> list[RagChunk]:
        if not settings.rag.rerank_enabled or len(chunks) <= 1:
            return sorted(chunks, key=lambda item: item.score, reverse=True)
        try:
            model = self._cross_encoder(settings.rag.rerank_model)
            scores = model.predict([(query_text, chunk.text) for chunk in chunks])
        except Exception:
            logger.exception("Reranking RAG fallito, uso score retrieval.")
            return sorted(chunks, key=lambda item: item.score, reverse=True)
        reranked: list[RagChunk] = []
        for chunk, score in zip(chunks, scores):
            normalized = _sigmoid(float(score))
            reranked.append(
                RagChunk(
                    text=chunk.text,
                    score=(chunk.score * 0.35) + (normalized * 0.65),
                    entry_id=chunk.entry_id,
                    entry_title=chunk.entry_title,
                    doc_type=chunk.doc_type,
                    source=chunk.source,
                )
            )
        return sorted(reranked, key=lambda item: item.score, reverse=True)

    def _cross_encoder(self, model_name: str):
        key = f"cross:{model_name}"
        with self._lock:
            existing = self._models.get(key)
            if existing is not None:
                return existing
            sentence_transformers = _import_sentence_transformers()
            model = sentence_transformers.CrossEncoder(model_name)
            self._models[key] = model
            return model


def _import_chromadb():
    try:
        import chromadb
    except ImportError as exc:
        raise ConfigurationError(
            "Dipendenza RAG mancante: chromadb.",
            detail="Installa le dipendenze aggiornate del progetto per abilitare il RAG.",
        ) from exc
    return chromadb


def _import_sentence_transformers():
    try:
        import sentence_transformers
    except ImportError as exc:
        raise ConfigurationError(
            "Dipendenza RAG mancante: sentence-transformers.",
            detail="Installa le dipendenze aggiornate del progetto per abilitare gli embedding locali.",
        ) from exc
    return sentence_transformers


def _chunk_to_docs(
    *,
    prefix: str,
    doc_type: str,
    source: str,
    text: str,
    entry: LibraryEntry,
    rag: RagSettings,
) -> list[_RagDoc]:
    chunks = chunk_text(text, size=rag.chunk_size_words, overlap=rag.chunk_overlap_words)
    return [
        _RagDoc(
            id=f"{prefix}:{chunk.index}",
            text=chunk.text,
            metadata=_metadata(entry, doc_type=doc_type, source=source, chunk_index=chunk.index),
        )
        for chunk in chunks
    ]


def _chunk_knowledge_file_to_docs(
    *,
    knowledge_file: WorkspaceKnowledgeFile,
    document: ExtractedDocument,
    rag: RagSettings,
) -> list[_RagDoc]:
    chunks = chunk_text(document.text, size=rag.chunk_size_words, overlap=rag.chunk_overlap_words)
    return [
        _RagDoc(
            id=f"knowledge:{knowledge_file.id}:{chunk.index}",
            text=chunk.text,
            metadata=_knowledge_metadata(
                knowledge_file,
                document,
                doc_type="knowledge_file",
                source=knowledge_file.original_name,
                chunk_index=chunk.index,
            ),
        )
        for chunk in chunks
    ]


def _metadata(
    entry: LibraryEntry,
    *,
    doc_type: str,
    source: str,
    chunk_index: int,
) -> dict[str, str | int | float | bool]:
    return {
        "workspace_id": entry.workspace_id,
        "entry_id": entry.id,
        "entry_title": entry.title,
        "recorded_on": entry.recorded_on.isoformat() if entry.recorded_on else "",
        "doc_type": doc_type,
        "source": source,
        "chunk_index": chunk_index,
    }


def _knowledge_metadata(
    knowledge_file: WorkspaceKnowledgeFile,
    document: ExtractedDocument,
    *,
    doc_type: str,
    source: str,
    chunk_index: int,
) -> dict[str, str | int | float | bool]:
    return {
        "workspace_id": knowledge_file.workspace_id,
        "entry_id": "",
        "entry_title": knowledge_file.original_name,
        "recorded_on": "",
        "doc_type": doc_type,
        "source": source,
        "chunk_index": chunk_index,
        "knowledge_file_id": knowledge_file.id,
        "knowledge_file_name": knowledge_file.original_name,
        "knowledge_folder": _knowledge_folder(knowledge_file.original_name),
        "knowledge_extension": knowledge_file.extension,
        "parser_source_type": document.source_type,
        "parser_page_count": document.page_count or 0,
        "parser_sheet_count": document.sheet_count or 0,
        "parser_row_count": document.row_count or 0,
    }


def _keyword_doc(doc: _RagDoc) -> dict[str, str]:
    return {
        "doc_id": doc.id,
        "workspace_id": str(doc.metadata.get("workspace_id") or ""),
        "entry_id": str(doc.metadata.get("entry_id") or doc.metadata.get("knowledge_file_id") or ""),
        "entry_title": str(doc.metadata.get("entry_title") or doc.metadata.get("knowledge_file_name") or ""),
        "doc_type": str(doc.metadata.get("doc_type") or ""),
        "source": str(doc.metadata.get("source") or ""),
        "knowledge_folder": str(doc.metadata.get("knowledge_folder") or ""),
        "content": doc.text,
    }


def _resolve_storage_path(rag: RagSettings) -> Path:
    if not rag.storage_dir.strip():
        base_path = RAG_DIR
    else:
        candidate = Path(rag.storage_dir)
        if candidate.is_absolute():
            base_path = candidate
        else:
            base_path = (DATA_DIR / candidate).resolve()
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path


def _embedding_text(text: str, *, is_query: bool, model: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return cleaned
    if model.startswith("intfloat/multilingual-e5"):
        prefix = "query: " if is_query else "passage: "
        return f"{prefix}{cleaned}"
    return cleaned


def _build_context_text(chunks: list[RagChunk], rag: RagSettings) -> str:
    lines: list[str] = []
    total = 0
    for chunk in chunks:
        line = (
            f"- [{chunk.doc_type} | {chunk.entry_title or chunk.entry_id} | {chunk.source}] "
            f"{chunk.text}"
        )
        if total + len(line) > rag.max_context_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def _build_where_filter(
    *,
    doc_types: list[str] | None,
    entry_ids: list[str] | None,
    knowledge_folders: list[str] | None,
) -> dict[str, object] | None:
    filters: list[dict[str, object]] = []
    clean_doc_types = [item for item in (doc_types or []) if item]
    clean_entry_ids = [item for item in (entry_ids or []) if item]
    clean_knowledge_folders = [item for item in (knowledge_folders or []) if item]
    if clean_doc_types:
        filters.append({"doc_type": {"$in": clean_doc_types}})
    if clean_entry_ids:
        filters.append({"entry_id": {"$in": clean_entry_ids}})
    if clean_knowledge_folders:
        filters.append({"knowledge_folder": {"$in": clean_knowledge_folders}})
    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def _knowledge_folder(original_name: str) -> str:
    normalized = original_name.replace("\\", "/").strip("/")
    if "/" not in normalized:
        return "File singoli"
    folder = normalized.rsplit("/", 1)[0].strip("/")
    return folder or "File singoli"


def _dedupe_chunks(chunks: list[RagChunk]) -> list[RagChunk]:
    best: dict[tuple[str, str, str], RagChunk] = {}
    for chunk in chunks:
        key = (chunk.entry_id, chunk.doc_type, clean_text(chunk.text, limit=240).lower())
        current = best.get(key)
        if current is None or chunk.score > current.score:
            best[key] = chunk
    return list(best.values())


def _sigmoid(value: float) -> float:
    if value < -40:
        return 0.0
    if value > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def _safe_collection_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        return "workspace_default"
    return normalized[:120]


def _join_non_empty(parts: list[str]) -> str:
    return "\n".join(part for part in parts if part and part.strip())
